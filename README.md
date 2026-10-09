# Popcorn.ai — live-catalog RAG movie/series concierge

```
text/🎤 ─► nlp.py      intent + language/type/runtime/genre/mood/"underrated"/title extraction
        ─► catalog.py  RECALL: TMDB discover/similar/search (any title) — offline catalog if no key
        ─► rag.py      RE-RANK: multilingual embeddings of candidate overviews vs your request
        ─► main.py     enrich top results (cast, runtime, trailer, where-to-watch)
        ─► llm.py      Claude answers ONLY from those results (grounded) 
        ─► web/        Netflix-style UI, trailer player, chat drawer, voice
```
## Setup
1. Free TMDB key: themoviedb.org → sign up → Settings → API → request a key. Put it in `.env` as `TMDB_API_KEY=...`
   (either the "API Key" or the long "API Read Access Token" works).
2. `pip install -r requirements.txt` then `python -m uvicorn app.main:app`  → http://localhost:8000
Read order: nlp.py → catalog.py → rag.py → llm.py → main.py → web/index.html. Tests: `pytest -q`.
