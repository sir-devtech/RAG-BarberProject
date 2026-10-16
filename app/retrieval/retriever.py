"""Orquestra a recuperacao: significado + palavras exatas + regra hibrida, para uma loja."""

from __future__ import annotations

from dataclasses import dataclass

from app.ingest.embeddings import Embedder, EmbeddingCache
from app.ingest.index import cached_query_vector
from app.retrieval.bm25 import Bm25Index
from app.retrieval.dense import DenseIndex
from app.retrieval.hit import Hit
from app.retrieval.hybrid import hybrid_search

POOL = 10  # candidatos de cada busca antes da fusao


@dataclass(frozen=True)
class Retrieval:
    hits: list[Hit]
    # Melhor cosseno da busca por significado: mede "o quanto a base fala disso".
    # Fica de fora do `hits` porque o score do hibrido (RRF) nao e comparavel a um limiar.
    best_similarity: float


class Retriever:
    def __init__(
        self,
        dense: DenseIndex,
        bm25: Bm25Index,
        embedder: Embedder,
        cache: EmbeddingCache,
        *,
        cache_queries: bool = True,
    ) -> None:
        self._cache_queries = cache_queries
        self._dense = dense
        self._bm25 = bm25
        self._embedder = embedder
        self._cache = cache

    def retrieve(self, question: str, tenant: str, *, top: int = 3) -> Retrieval:
        if self._cache_queries:
            vector = cached_query_vector(self._embedder, self._cache, question)
        else:  # API publica: o embedder ja tem memoria limitada
            vector = self._embedder.embed_query(question)
        dense_hits = self._dense.search(vector, tenant=tenant, k=POOL)
        bm25_hits = self._bm25.search(question, tenant=tenant, k=POOL)
        return Retrieval(
            hits=hybrid_search(dense_hits, bm25_hits, top=top),
            best_similarity=dense_hits[0].score if dense_hits else 0.0,
        )
