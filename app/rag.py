"""Step 2 - Retrieve-then-rerank: embed candidate overviews and score them against the request."""
import os, random
import numpy as np
from .nlp import Query


def doc(i: dict) -> str:
    return f"{i['title']} ({i['year']}) {i['media']} in {i['language']}. Genres: {', '.join(i['genres'])}. {i['overview']}"


class Ranker:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"))
        self.cache = {}                                   # item id -> embedding

    def _vecs(self, items):
        miss = [i for i in items if i["id"] not in self.cache]
        if miss:
            for i, e in zip(miss, self.model.encode([doc(i) for i in miss], normalize_embeddings=True)):
                self.cache[i["id"]] = e
        return np.stack([self.cache[i["id"]] for i in items])

    def rank(self, q: Query, cands, anchor=None, seen=(), k=5):
        if not cands:
            return []
        qv = self.model.encode([q.text + " " + " ".join(q.genres | q.moods)], normalize_embeddings=True)[0]
        if anchor is not None:                            # "something like X": blend X's meaning into the query
            qv = qv + self._vecs([anchor])[0]
            qv /= np.linalg.norm(qv)
        sims = self._vecs(cands) @ qv
        out = []
        for it, s in zip(cands, sims):
            if (anchor and it["id"] == anchor["id"]) or (q.more and it["id"] in seen):
                continue
            g = set(it["genres"])
            m, h = q.genres & g, q.hint_genres & g
            score = float(s) + .15 * len(m) + .07 * len(h) + .02 * it["rating"] + random.random() * .05
            score -= .2 if it["id"] in seen else 0
            out.append(({**it, "why": ", ".join(sorted(m | h)) or f"semantic match {s:.2f}"}, score))
        out.sort(key=lambda x: -x[1])
        return [o[0] for o in out[:k]]
