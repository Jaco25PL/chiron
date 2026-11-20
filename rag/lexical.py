"""Keyword search (BM25) over the course chunks, for the "hibrida" mode of rag/search.py (not the default:
see FINDINGS #28).

Embeddings match meaning, so they blur exact terms the notes use as names: "punto de Surraco",
"monofilamento", "Lasègue". BM25 ranks by the query's words, weighting rare ones more (IDF), which is
exactly what those questions need. It runs in memory (1340 chunks, built once per process); Postgres'
own full-text search was the other option, but its ranking has no IDF and this database has no
`unaccent`, so "Lasègue" and "Lasegue" wouldn't match.

Tokens: lowercase, no accents, words of 2+ letters or digits, Spanish stopwords out, and a crude
stemmer that keeps the first STEM characters ("diabético", "diabética", "diabetes" -> "diabet"), enough
for a language with long suffixes and far simpler than a real one.
"""

import math
import re
import unicodedata
from collections import Counter

STEM = 6
K1, B = 1.2, 0.75  # the usual BM25 parameters

STOPWORDS = set("""
a al algo algun alguna alguno algunos ante antes aqui asi cada como con contra cual cuales cuando cuanto
cuanta cuantos cuantas de del desde donde dos e el ella ellas ello ellos en entre era eran es esa esas ese
eso esos esta estaba estan estar estas este esto estos fue fueron ha habia han hay hace hacer hacen la las
le les lo los mas me mi mis muy nada ni no nos o os otra otro otros para pero poco por porque que quien
se ser si sin sobre son su sus tambien te tiene tienen tengo tu tus un una uno unos unas y ya yo vos
usted ustedes eh dale bueno ahora entonces era sea ese esa mismo misma cosa cosas
sirve sirven hago hacemos ver veo viene vienen pido pedir puedo puede debo debe dice dijo llama llaman
sabe saber quiero queda pasa pasaba significa cual es eso aca ahi alla
""".split())  # last two lines: the verbs of a question ("¿para qué sirve...?", "¿cómo se llama...?")


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", text)
    return [w[:STEM] for w in words if len(w) >= 2 and w not in STOPWORDS]


class BM25:
    """BM25 over `docs` ([{id, texto, tipo}]); `top` returns ids, best first, only docs sharing a token."""

    def __init__(self, docs: list[dict]):
        self.ids = [d["id"] for d in docs]
        self.tipos = [d.get("tipo") for d in docs]
        self.tf = [Counter(tokens(d["texto"])) for d in docs]
        self.len = [sum(tf.values()) for tf in self.tf]
        self.avg = sum(self.len) / max(len(docs), 1)
        df = Counter(t for tf in self.tf for t in tf)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = set(tokens(query))
        out = []
        for tf, length in zip(self.tf, self.len):
            s = 0.0
            for t in q & tf.keys():
                f = tf[t]
                s += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * length / self.avg))
            out.append(s)
        return out

    def top(self, query: str, n: int, tipo: str | None = None) -> list[str]:
        ranked = sorted(
            ((s, i) for i, s in enumerate(self.scores(query)) if s > 0 and (tipo is None or self.tipos[i] == tipo)),
            reverse=True,
        )
        return [self.ids[i] for _, i in ranked[:n]]
