"""Candidate generation: live TMDB when a key is set, otherwise the bundled offline catalog."""
import json
from difflib import SequenceMatcher
from pathlib import Path
from . import tmdb
from .nlp import Query

_LOCAL = None


def local():
    global _LOCAL
    if _LOCAL is None:
        raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "movies.json").read_text(encoding="utf-8"))
        _LOCAL = [{"id": f"local:{m['id']}", "tmdb_id": None, "media": "movie" if m["type"] == "movie" else "tv",
                   "title": m["title"], "year": str(m["year"]), "language": m["language"], "genres": m["genres"],
                   "overview": m["summary"], "rating": m["rating"], "votes": 0, "poster": None, "backdrop": None,
                   "runtime": m["minutes"], "cast": m["cast"], "trailer": None, "providers": {}, "seasons": m["seasons"]}
                  for m in raw]
    return _LOCAL


def resolve(cands):
    """Find the title the user mentioned (TMDB if available, else offline catalog)."""
    if not cands:
        return None
    if tmdb.enabled():
        try:
            return tmdb.resolve_title(cands)
        except Exception as e:
            print("TMDB resolve error:", e)
    best, score = None, 0.72
    for c in cands:
        for it in local():
            r = SequenceMatcher(None, c.lower(), it["title"].lower()).ratio()
            if r > score:
                best, score = it, r
    return best


def _local_candidates(q: Query):
    for relax in range(3):
        out = [x for x in local() if (not q.lang or x["language"] == q.lang or relax > 1)
               and (not q.type or x["media"] == ("movie" if q.type == "movie" else "tv") or relax > 0)]
        if len(out) >= 3:
            return out
    return local()


def candidates(q: Query, ref=None):
    """Recall step: gather a pool of plausible titles; the Ranker re-ranks them semantically."""
    if tmdb.enabled():
        try:
            medias = ["movie"] if q.type == "movie" else ["tv"] if q.type == "series" else ["movie", "tv"]
            genres = q.genres or q.hint_genres
            out = tmdb.similar(ref) if ref else []
            for m in medias:
                kw = dict(lang=q.lang, genres=genres, max_min=q.max_min)
                if q.underrated:      # hidden gems: great rating but few votes
                    kw.update(sort="vote_average.desc", min_votes=120, max_votes=2500, min_rating=7.2)
                elif q.quality:
                    kw.update(sort="vote_average.desc", min_votes=1000)
                else:
                    kw.update(sort="popularity.desc", min_votes=150)
                out += tmdb.discover(m, **kw)
            if not (q.genres or q.lang or q.underrated or ref):   # vague/free text: add text-search recall
                out += tmdb.search(q.text)[:8] + [x for m in medias for x in tmdb.trending(m)]
            seen, uniq = set(), []
            for x in out:
                if x["id"] not in seen:
                    seen.add(x["id"]); uniq.append(x)
            if uniq:
                return uniq, "tmdb"
        except Exception as e:
            print("TMDB error, using offline catalog:", e)
    return _local_candidates(q), "local"
