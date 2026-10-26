"""Lokalny magazyn wektorowy (zamiennik embeddingów) + proste przetwarzanie tekstu.

W rozwiązaniu produkcyjnym ten moduł zastępuje się embeddingami (OpenAI
text-embedding-3-small) i Qdrantem/Chroma. Tutaj, aby rozwiązanie działało
offline, używamy wektoryzacji worka słów z haszowaniem cech i TF-IDF oraz
cosinusowej miary podobieństwa - mechanika wyszukiwania jest ta sama.
"""
from __future__ import annotations

import math
import re
from collections import Counter

DIM = 512
WORD_RE = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9]{2,}")


def stem(token: str, n: int = 6) -> str:
    """Prymitywny rdzeń: pierwsze n znaków (prototyp/prototypowego -> protot)."""
    return token.lower()[:n]


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in WORD_RE.findall(text)]


def chunks(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    """Dzieli dokument na fragmenty po granicach akapitu (podstawowy chunking)."""
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(cur) + len(para) > size and cur:
            parts.append(cur.strip())
            cur = cur[-overlap:] if overlap else ""
        cur += "\n" + para
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _hash(token: str) -> int:
    h = 2166136261
    for ch in token:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % DIM


class Index:
    """Mini-baza wektorowa: dokumenty + wektory + metadane + wyszukiwanie top-k."""

    def __init__(self) -> None:
        self.docs: list[dict] = []
        self.vectors: list[dict[int, float]] = []
        self.df: Counter = Counter()

    def add(self, text: str, **meta) -> None:
        counts = Counter(tokenize(text))
        if not counts:
            return
        idx = len(self.docs)
        self.docs.append({"text": text, **meta})
        self.vectors.append({})
        self._pending = getattr(self, "_pending", [])
        self._pending.append((idx, counts))
        for token in counts:
            self.df[token] += 1

    def build(self) -> None:
        n = max(1, len(self.docs))
        for idx, counts in getattr(self, "_pending", []):
            total = sum(counts.values())
            vec = {}
            for token, cnt in counts.items():
                idf = math.log(1 + n / (1 + self.df[token]))
                vec[_hash(token)] = vec.get(_hash(token), 0.0) + (cnt / total) * idf
            self.vectors[idx] = _normalize(vec)
        self._pending = []

    def search(self, query: str, expand: dict[str, list[str]] | None = None,
               limit: int = 5) -> list[tuple[float, dict]]:
        tokens = tokenize(query)
        if expand:
            extra = []
            for tok in list(tokens):
                for key, syns in expand.items():
                    if tok.startswith(key[:6]):
                        extra += [stem(s) for s in syns]
            tokens += extra
        counts = Counter(tokens)
        qvec = _normalize({_hash(t): c / max(1, sum(counts.values())) for t, c in counts.items()})
        scored = []
        for idx, vec in enumerate(self.vectors):
            if not vec:
                continue
            dot = sum(w * vec.get(k, 0.0) for k, w in qvec.items())
            scored.append((dot, self.docs[idx]))
        scored.sort(key=lambda p: p[0], reverse=True)
        return scored[:limit]


def _normalize(vec: dict[int, float]) -> dict[int, float]:
    norm = math.sqrt(sum(v * v for v in vec.values()))
    return {k: v / norm for k, v in vec.items()} if norm else {}


def extract_date(text: str) -> str | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", text)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
