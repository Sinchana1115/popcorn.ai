"""Step 1 - NLP query understanding: intent + entities (language, type, runtime, genre, mood, title, 'underrated')."""
import re
from dataclasses import dataclass, field
from typing import List, Optional

LANGS = {"hindi": "Hindi", "bollywood": "Hindi", "tamil": "Tamil", "telugu": "Telugu", "kannada": "Kannada",
         "malayalam": "Malayalam", "english": "English", "hollywood": "English", "korean": "Korean",
         "japanese": "Japanese", "anime": "Japanese", "spanish": "Spanish", "french": "French", "german": "German"}
GENRES = {"comedy": "Comedy", "funny": "Comedy", "laugh": "Comedy", "horror": "Horror", "scary": "Horror",
          "romance": "Romance", "romantic": "Romance", "love": "Romance", "thriller": "Thriller",
          "suspense": "Thriller", "action": "Action", "sci-fi": "Sci-Fi", "scifi": "Sci-Fi", "space": "Sci-Fi",
          "drama": "Drama", "animation": "Animation", "animated": "Animation", "anime": "Animation",
          "mystery": "Mystery", "crime": "Crime", "heist": "Crime", "family": "Family", "kids": "Family",
          "fantasy": "Fantasy", "music": "Music", "sports": "Drama", "war": "War"}
MOODS = {"cry": "emotional", "sad": "emotional", "emotional": "emotional", "heartwarming": "feelgood",
         "feel good": "feelgood", "feel-good": "feelgood", "happy": "feelgood", "mind": "mindbending",
         "twist": "twist", "binge": "binge", "relax": "light", "light": "light", "chill": "light",
         "dark": "dark", "gritty": "dark", "intense": "intense", "classic": "classic"}
MOOD_GENRES = {"emotional": {"Drama", "Romance"}, "feelgood": {"Comedy", "Family"},
               "mindbending": {"Sci-Fi", "Mystery", "Thriller"}, "twist": {"Mystery", "Thriller"},
               "dark": {"Crime", "Thriller", "Horror"}, "intense": {"Action", "Thriller"}, "light": {"Comedy"}}
INFO = re.compile(r"\b(about|cast|actors?|stars?|starring|who|summary|plot|story|synopsis|duration|how long|"
                  r"runtime|length|rating|rated|worth|details?|episodes?|seasons?)\b")
MORE = re.compile(r"\b(another|more|else|different|next)\b")
GREET = re.compile(r"^\s*(hi|hello|hey|namaste|yo)\b", re.I)
UNDER = re.compile(r"\b(underrated|hidden gems?|lesser[- ]known|overlooked|under the radar)\b")
QUALITY = re.compile(r"\b(best|top rated|highest rated|critically acclaimed|award[- ]winning|must[- ]watch)\b")
TITLE_PATTERNS = [
    r'"([^"]{2,60})"',
    r"\b(?:like|similar to|reminds? me of|after watching)\s+(.+)",
    r"\b(?:how long is|how long does|runtime of|duration of|cast of|cast in|actors? (?:in|of)|who (?:is|are|was|stars?|"
    r"acted|plays?) in|summary of|plot of|story of|synopsis of|rating of|tell me about|details (?:of|on|about)|"
    r"info (?:on|about)|about)\s+(.+)",
]


@dataclass
class Query:
    text: str
    lang: Optional[str] = None
    type: Optional[str] = None          # "movie" | "series"
    max_min: Optional[int] = None
    genres: set = field(default_factory=set)
    moods: set = field(default_factory=set)
    hint_genres: set = field(default_factory=set)   # genres implied by mood words
    intent: str = "recommend"           # recommend | info | smalltalk
    title_cands: List[str] = field(default_factory=list)   # possible title mentions (verified later vs the catalog)
    more: bool = False
    underrated: bool = False
    quality: bool = False


def norm(s: str) -> str:
    return " " + re.sub(r"[^\w\- ]+", " ", s.lower()).strip() + " "


def extract_titles(text: str) -> List[str]:
    """Candidate title strings. Verified later against TMDB, so false positives are harmless."""
    t = text.replace("\u201c", '"').replace("\u201d", '"')
    for p in TITLE_PATTERNS:
        m = re.search(p, t, re.I)
        if m:
            s = re.sub(r"[?.!,;:]+$", "", m.group(1).strip())
            s = re.sub(r"\b(movie|film|series|show|please|worth watching|worth it)\b.*$", "", s, flags=re.I).strip()
            cut = re.split(r"\s+(?:under|in|with|that|but|and|which|for|from|on)\s+", s, maxsplit=1, flags=re.I)[0].strip()
            return [x for x in dict.fromkeys([s, cut]) if len(x) > 1]
    return []


def parse(text: str, ui_lang=None, ui_type=None) -> Query:
    q = norm(text)
    out = Query(text=text, lang=ui_lang, type=ui_type)
    for k, v in LANGS.items():
        if " " + k in q:
            out.lang = v
    if re.search(r" (series|show|shows|season|binge) ", q):
        out.type = "series"
    elif re.search(r" (movie|movies|film|films) ", q):
        out.type = "movie"
    out.genres = {v for k, v in GENRES.items() if " " + k in q}
    out.moods = {v for k, v in MOODS.items() if " " + k in q}
    for m in out.moods:
        out.hint_genres |= MOOD_GENRES.get(m, set())
    m = re.search(r"(under|less than|below|within|upto|up to)\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?)", q)
    if m:
        n = float(m[2])
        out.max_min = int(n * 60) if m[3].startswith("h") else int(n)
    elif re.search(r" (short|quick|brief) ", q):
        out.max_min = 110
    out.more = bool(MORE.search(q))
    out.underrated = bool(UNDER.search(q))
    out.quality = bool(QUALITY.search(q))
    out.title_cands = extract_titles(text)
    if out.title_cands and INFO.search(q) and not re.search(r"\b(like|similar)\b", q):
        out.intent = "info"
    elif GREET.match(text) and not (out.genres or out.moods or out.lang or out.title_cands):
        out.intent = "smalltalk"
    return out
