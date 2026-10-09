"""Live catalog from TMDB: any movie/series, posters, cast, trailers (YouTube keys), where-to-watch."""
import os, time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

BASE, IMG = "https://api.themoviedb.org/3", "https://image.tmdb.org/t/p"
LANG_CODE = {"Hindi": "hi", "Tamil": "ta", "Telugu": "te", "Kannada": "kn", "Malayalam": "ml", "English": "en",
             "Korean": "ko", "Japanese": "ja", "Spanish": "es", "French": "fr", "German": "de"}
CODE_LANG = {v: k for k, v in LANG_CODE.items()}
GENRE_NAMES = {28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime", 99: "Documentary",
               18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
               9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 53: "Thriller", 10752: "War", 37: "Western",
               10759: "Action", 10762: "Kids", 10765: "Sci-Fi", 10768: "War"}
GENRE_IDS = {
    "movie": {"Action": "28", "Animation": "16", "Comedy": "35", "Crime": "80", "Drama": "18", "Family": "10751",
              "Fantasy": "14", "Horror": "27", "Music": "10402", "Mystery": "9648", "Romance": "10749",
              "Sci-Fi": "878", "Thriller": "53", "War": "10752"},
    "tv": {"Action": "10759", "Animation": "16", "Comedy": "35", "Crime": "80", "Drama": "18", "Family": "10751",
           "Fantasy": "10765", "Mystery": "9648", "Sci-Fi": "10765", "Thriller": "9648|80", "War": "10768"}}
_cache = {}


def enabled():
    return bool(os.getenv("TMDB_API_KEY"))


def _get(path, **params):
    params = {k: v for k, v in params.items() if v is not None}
    ck = (path, tuple(sorted(params.items())))
    hit = _cache.get(ck)
    if hit and time.time() - hit[0] < 900:                       # 15-min cache keeps it fast + under rate limits
        return hit[1]
    import httpx
    key, headers = os.getenv("TMDB_API_KEY", ""), {}
    if key.startswith("eyJ"):                                    # v4 "Read Access Token"
        headers["Authorization"] = "Bearer " + key
    else:                                                        # v3 API key
        params["api_key"] = key
    r = httpx.get(BASE + path, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    _cache[ck] = (time.time(), r.json())
    return _cache[ck][1]


def img(p, size):
    return f"{IMG}/{size}{p}" if p else None


def norm(r, media=None):
    media = media or r.get("media_type") or ("tv" if "name" in r else "movie")
    if media not in ("movie", "tv"):
        return None
    date = r.get("release_date") or r.get("first_air_date") or ""
    names = [GENRE_NAMES[g] for g in r.get("genre_ids", []) if g in GENRE_NAMES] or [g["name"] for g in r.get("genres", [])]
    return {"id": f"{media}:{r['id']}", "tmdb_id": r["id"], "media": media, "title": r.get("title") or r.get("name") or "",
            "year": date[:4], "language": CODE_LANG.get(r.get("original_language"), (r.get("original_language") or "").upper()),
            "genres": list(dict.fromkeys(names)), "overview": r.get("overview", ""),
            "rating": round(r.get("vote_average") or 0, 1), "votes": r.get("vote_count") or 0,
            "poster": img(r.get("poster_path"), "w342"), "backdrop": img(r.get("backdrop_path"), "w1280")}


def _list(data, media=None):
    out = [norm(r, media) for r in data.get("results", [])]
    return [x for x in out if x and x["overview"]]


def discover(media, lang=None, genres=(), max_min=None, sort="popularity.desc", min_votes=100, max_votes=None, min_rating=None):
    gid = "|".join(GENRE_IDS[media][g] for g in genres if g in GENRE_IDS[media]) or None
    return _list(_get(f"/discover/{media}", sort_by=sort, include_adult="false", language="en-US",
                      with_original_language=LANG_CODE.get(lang), with_genres=gid, **{"with_runtime.lte": max_min},
                      **{"vote_count.gte": min_votes, "vote_count.lte": max_votes, "vote_average.gte": min_rating}), media)


def trending(media):
    return _list(_get(f"/trending/{media}/week"), media)


def similar(item):
    m, i = item["media"], item["tmdb_id"]
    return _list(_get(f"/{m}/{i}/recommendations"), m) + _list(_get(f"/{m}/{i}/similar"), m)


def search(text):
    return _list(_get("/search/multi", query=text, include_adult="false"))


def resolve_title(cands):
    """Return the catalog title best matching any candidate string (fuzzy), or None."""
    best, score = None, 0.72
    for c in cands:
        for it in search(c)[:6]:
            r = SequenceMatcher(None, c.lower(), it["title"].lower()).ratio()
            if r > score:
                best, score = it, r
    return best


def details(media, tid):
    d = _get(f"/{media}/{tid}", append_to_response="credits,videos,watch/providers", language="en-US",
             include_video_language="en,hi,ta,te,kn,ml,null")
    it = norm(d, media)
    vids = [v for v in d.get("videos", {}).get("results", []) if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser")]
    vids.sort(key=lambda v: (v["type"] != "Trailer", not v.get("official", False)))
    reg = d.get("watch/providers", {}).get("results", {}).get(os.getenv("TMDB_REGION", "IN"), {})
    crew = [c["name"] for c in d.get("credits", {}).get("crew", []) if c.get("job") == "Director"][:2]
    it.update({"runtime": d.get("runtime") or (d.get("episode_run_time") or [None])[0],
               "seasons": d.get("number_of_seasons"), "tagline": d.get("tagline", ""),
               "cast": [c["name"] for c in d.get("credits", {}).get("cast", [])[:7]],
               "director": crew or [c["name"] for c in d.get("created_by", [])],
               "trailer": vids[0]["key"] if vids else None,
               "providers": {k: [p["provider_name"] for p in reg.get(k, [])] for k in ("flatrate", "rent", "buy")}})
    return it


def home(lang=None, typ=None):
    medias = ["movie"] if typ == "movie" else ["tv"] if typ == "series" else ["movie", "tv"]
    jobs, L = [], f" in {lang}" if lang else ""
    for m in medias:
        lab = "Movies" if m == "movie" else "Series"
        jobs += [(f"Trending {lab}{L}", lambda m=m: trending(m) if not lang else discover(m, lang=lang)),
                 (f"Top Rated {lab}{L}", lambda m=m: discover(m, lang=lang, sort="vote_average.desc", min_votes=150 if lang and lang != "English" else 800)),
                 (f"Hidden Gems: {lab}{L}", lambda m=m: discover(m, lang=lang, sort="vote_average.desc", min_votes=120, max_votes=2500, min_rating=7.2))]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: j[1](), jobs))
    return [{"name": j[0], "items": r} for j, r in zip(jobs, res) if r]
