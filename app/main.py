"""FastAPI app. Per message: NLP parse -> candidate recall (TMDB) -> semantic re-rank -> enrich -> LLM answer."""
import os, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()
from . import catalog, llm, nlp, stt, tmdb   # noqa: E402
from .rag import Ranker                        # noqa: E402

app = FastAPI(title="Popcorn.ai")
ranker = Ranker()


class ChatIn(BaseModel):
    message: str
    history: List[dict] = []
    lang: Optional[str] = None
    type: Optional[str] = None
    seen: List[str] = []
    use_llm: bool = True


@app.get("/api/config")
def config():
    return {"tmdb": tmdb.enabled(), "llm": bool(os.getenv("ANTHROPIC_API_KEY"))}


@app.get("/api/home")
def home(lang: str = "", type: str = ""):
    if tmdb.enabled():
        try:
            return tmdb.home(lang or None, type or None)
        except Exception as e:
            print("TMDB home error:", e)
    items = [x for x in catalog.local() if (not lang or x["language"] == lang)
             and (not type or x["media"] == ("movie" if type == "movie" else "tv"))]
    return [{"name": "Offline catalog (add TMDB_API_KEY for the full live catalog)", "items": items}] if items else []


@app.get("/api/title/{media}/{tid}")
def title(media: str, tid: int):
    if media not in ("movie", "tv"):
        raise HTTPException(400, "bad media type")
    try:
        return tmdb.details(media, tid)
    except Exception as e:
        raise HTTPException(502, str(e))


def enrich(items):
    """Fetch cast / runtime / trailer for the top results (parallel)."""
    def one(it):
        if it["id"].startswith("local:") or not tmdb.enabled():
            return it
        try:
            return {**tmdb.details(it["media"], it["tmdb_id"]), "why": it.get("why", "")}
        except Exception:
            return it
    with ThreadPoolExecutor(5) as ex:
        return list(ex.map(one, items))


@app.post("/api/chat")
def chat(b: ChatIn):
    q = nlp.parse(b.message, b.lang, b.type)
    if q.intent == "smalltalk":
        return {"reply": "Hey! Tell me your mood, language, or ask for underrated gems 🍿", "items": []}
    seen = set(b.seen)
    ref = catalog.resolve(q.title_cands)
    if q.intent == "info" and not ref:
        q.intent = "recommend"
    cands, source = catalog.candidates(q, ref)
    top = ranker.rank(q, cands, anchor=ref, seen=seen, k=5)
    if q.intent == "info":
        top = [{**ref, "why": "requested title"}] + top[:2]
    top = enrich(top)
    if not top:
        return {"reply": "I couldn't find a match. Try another language or genre!", "items": []}
    res = llm.answer(b.message, b.history, q, top, b.use_llm)
    byid = {i["id"]: i for i in top}
    ids = res["ids"] or [i["id"] for i in top[:3]]
    return {"reply": res["reply"], "items": [byid[i] for i in ids if i in byid], "source": source,
            "parsed": {**q.__dict__, "genres": sorted(q.genres), "moods": sorted(q.moods), "hint_genres": sorted(q.hint_genres)}}


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), lang: Optional[str] = Form(None)):
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(await file.read())
    try:
        text, detected = stt.transcribe(f.name, lang)
        return {"text": text, "language": detected}
    except Exception as e:
        return {"text": "", "error": str(e)}
    finally:
        os.unlink(f.name)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True), name="web")
