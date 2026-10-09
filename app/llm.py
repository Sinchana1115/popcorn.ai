"""Step 3 - Generation: Claude answers using ONLY the retrieved titles (grounded RAG)."""
import json, os, re
from .nlp import Query

SYSTEM = """You are Popcorn.ai, a friendly movie/series concierge.
Use ONLY the CONTEXT titles. Never invent titles, cast or runtimes; if something is not in the context, say so.
Reply in the language the user wrote in. For recommendations choose up to 3 ids from the context with a one-line
reason each (for 'underrated' requests mention that it has a high rating but fewer votes). For questions about one
title, answer precisely (runtime, cast, summary, rating). Return ONLY JSON: {"reply": "...", "ids": ["id", ...]}"""


def context(items):
    return "\n".join(f"[id={m['id']}] {m['title']} ({m['year']}, {'series' if m['media'] == 'tv' else 'movie'}, "
                     f"{m['language']}) | genres: {', '.join(m['genres'])} | rating {m['rating']} ({m['votes']} votes) | "
                     f"runtime: {m.get('runtime') or 'unknown'} min | cast: {', '.join(m.get('cast') or []) or 'unknown'} | "
                     f"{m['overview'][:350]}" for m in items)


def fallback(q: Query, items):
    if q.intent == "info":
        m = items[0]
        return {"reply": f"{m['title']} ({m['year']}): {m['overview']} Rating {m['rating']}.", "ids": [m["id"]]}
    return {"reply": "Here are my top picks for you:", "ids": [i["id"] for i in items[:3]]}


def answer(message, history, q: Query, items, use_llm=True):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not (use_llm and key):
        return fallback(q, items)
    import anthropic
    msgs = [h for h in history if h.get("role") in ("user", "assistant")]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    msgs.append({"role": "user", "content": f"CONTEXT:\n{context(items)}\n\nUSER: {message}"})
    try:
        r = anthropic.Anthropic(api_key=key).messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"), max_tokens=700, system=SYSTEM, messages=msgs)
        data = json.loads(re.search(r"\{.*\}", r.content[0].text, re.S).group(0))
        valid = {i["id"] for i in items}
        data["ids"] = [i for i in data.get("ids", []) if i in valid][:3]
        return data
    except Exception as e:
        print("LLM error:", e)
        return fallback(q, items)
