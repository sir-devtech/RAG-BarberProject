"""Resultado de uma busca, comum a todos os tipos de busca."""

from __future__ import annotations

from dataclasses import dataclass

from app.ingest.chunking import Chunk


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float  # a escala depende da busca (cosseno, BM25, RRF): so compare dentro da mesma
