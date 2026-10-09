from app.nlp import parse
from app import tmdb


def test_filters():
    q = parse("a funny Hindi movie under 2 hours")
    assert q.lang == "Hindi" and q.type == "movie" and q.max_min == 120 and "Comedy" in q.genres


def test_info_intent():
    q = parse("how long is Inception?")
    assert q.intent == "info" and q.title_cands[0] == "Inception"


def test_like_is_recommend():
    q = parse("something like Dark")
    assert q.intent == "recommend" and q.title_cands == ["Dark"]


def test_title_with_constraint():
    assert parse("tell me about Gully Boy in Hindi").title_cands == ["Gully Boy in Hindi", "Gully Boy"]


def test_underrated():
    q = parse("underrated Tamil thriller under 150 minutes")
    assert q.underrated and q.lang == "Tamil" and q.max_min == 150 and "Thriller" in q.genres


def test_greeting():
    assert parse("hi").intent == "smalltalk"


def test_tmdb_normalize():
    it = tmdb.norm({"id": 1, "title": "X", "release_date": "2019-05-01", "genre_ids": [35, 18], "original_language": "hi",
                    "overview": "o", "vote_average": 7.84, "vote_count": 10, "poster_path": "/p.jpg"}, "movie")
    assert it["id"] == "movie:1" and it["language"] == "Hindi" and it["genres"] == ["Comedy", "Drama"]
    assert it["poster"].endswith("/w342/p.jpg") and it["rating"] == 7.8
