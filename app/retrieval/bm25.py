"""BM25: busca por palavras exatas, escrita a mao para ser explicavel.

pontuacao(chunk) = soma, para cada palavra da pergunta, de:
    IDF(palavra) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * tamanho / tamanho_medio))
- tf: quantas vezes a palavra aparece no chunk (com retorno decrescente, pelo k1).
- IDF: raridade da palavra na base DA LOJA. Palavra em todo chunk vale quase 0.
- b: quanto penalizar chunks longos.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.ingest.chunking import Chunk
from app.retrieval.hit import Hit
from app.retrieval.text import tokenize


@dataclass
class _Corpus:
    chunks: list[Chunk] = field(default_factory=list)
    term_counts: list[Counter[str]] = field(default_factory=list)
    lengths: list[int] = field(default_factory=list)
    idf: dict[str, float] = field(default_factory=dict)
    avg_length: float = 1.0


class Bm25Index:
    def __init__(self, chunks: Sequence[Chunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        # Um corpus por loja: as estatisticas (IDF, tamanho medio) nunca misturam lojas.
        self._corpora: dict[str, _Corpus] = {}
        for chunk in chunks:
            corpus = self._corpora.setdefault(chunk.tenant, _Corpus())
            tokens = tokenize(chunk.text)
            corpus.chunks.append(chunk)
            corpus.term_counts.append(Counter(tokens))
            corpus.lengths.append(len(tokens))
        for corpus in self._corpora.values():
            total = len(corpus.chunks)
            corpus.avg_length = max(sum(corpus.lengths) / total, 1.0)
            containing: Counter[str] = Counter()
            for counts in corpus.term_counts:
                containing.update(counts.keys())
            corpus.idf = {
                term: math.log(1 + (total - n + 0.5) / (n + 0.5)) for term, n in containing.items()
            }

    def search(self, query: str, *, tenant: str, k: int = 3) -> list[Hit]:
        corpus = self._corpora.get(tenant)
        if corpus is None:
            return []
        terms = [t for t in dict.fromkeys(tokenize(query)) if t in corpus.idf]
        scored: list[Hit] = []
        for chunk, counts, length in zip(
            corpus.chunks, corpus.term_counts, corpus.lengths, strict=True
        ):
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf:
                    norm = tf + self._k1 * (1 - self._b + self._b * length / corpus.avg_length)
                    score += corpus.idf[term] * tf * (self._k1 + 1) / norm
            if score > 0:
                scored.append(Hit(chunk, score))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:k]
