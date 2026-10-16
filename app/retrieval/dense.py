"""Busca densa: compara o significado da pergunta com o dos chunks (similaridade de cosseno)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.ingest.chunking import Chunk
from app.ingest.embeddings import Matrix


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float  # cosseno: 1 = mesmo sentido, perto de 0 = sem relacao


class DenseIndex:
    def __init__(self, chunks: Sequence[Chunk], vectors: Matrix) -> None:
        if vectors.shape[0] != len(chunks):
            raise ValueError("Deve haver um vetor por chunk")
        self._chunks = list(chunks)
        self._vectors = vectors

    def search(
        self, query_vector: Matrix, *, tenant: str, k: int = 3, min_score: float = 0.0
    ) -> list[Hit]:
        """Top-k chunks da loja `tenant`. O filtro por loja vem ANTES da comparacao."""
        rows = [i for i, chunk in enumerate(self._chunks) if chunk.tenant == tenant]
        if not rows:
            return []
        scores = self._vectors[rows] @ query_vector.reshape(-1)
        best = np.argsort(-scores)[:k]
        return [
            Hit(self._chunks[rows[j]], float(scores[j])) for j in best if scores[j] >= min_score
        ]
