"""Gera (ou reaproveita do cache) os vetores de uma lista de chunks."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.ingest.chunking import Chunk
from app.ingest.embeddings import EmbeddingCache, GeminiEmbedder, Matrix


def embed_chunks(
    chunks: Sequence[Chunk], embedder: GeminiEmbedder, cache: EmbeddingCache
) -> Matrix:
    """Devolve uma matriz (chunks x dimensoes). So chama a API para textos novos ou alterados."""
    keys = [
        EmbeddingCache.key(embedder.model, embedder.dimensions, chunk.content_hash)
        for chunk in chunks
    ]
    missing = [i for i, key in enumerate(keys) if cache.get(key) is None]
    if missing:
        fresh = embedder.embed_documents([chunks[i].text for i in missing])
        for i, vector in zip(missing, fresh, strict=True):
            cache.put(keys[i], vector.tolist())
        cache.save()
    vectors: list[list[float]] = []
    for key in keys:
        cached = cache.get(key)
        if cached is None:  # nao acontece: acabamos de preencher
            raise RuntimeError("cache incompleto")
        vectors.append(cached)
    return np.array(vectors, dtype=np.float32)
