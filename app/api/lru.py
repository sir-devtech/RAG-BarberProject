"""Memoria limitada para vetores de perguntas.

Cache sem limite numa API publica e um vazamento de memoria provocavel: bastaria enviar
milhares de perguntas diferentes. Aqui o teto e fixo; o item mais antigo sai primeiro.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Sequence

from app.ingest.embeddings import Embedder, Matrix


class LruQueryEmbedder:
    def __init__(self, inner: Embedder, maxsize: int = 256) -> None:
        if maxsize < 1:
            raise ValueError("maxsize >= 1")
        self._inner = inner
        self._maxsize = maxsize
        self._cache: OrderedDict[str, Matrix] = OrderedDict()
        self._lock = threading.Lock()
        self.model = inner.model
        self.dimensions = inner.dimensions

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> Matrix:
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
        vector = self._inner.embed_query(text)  # fora do lock: a chamada de rede e lenta
        with self._lock:
            self._cache[text] = vector
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)
        return vector

    def __len__(self) -> int:
        return len(self._cache)
