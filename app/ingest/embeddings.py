"""Cliente de embeddings do Gemini, com retentativa e cache por hash do texto.

Embedding = lista de numeros que representa o SIGNIFICADO de um texto. Textos de sentido
parecido ficam com vetores proximos, mesmo sem palavras em comum.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np
from numpy.typing import NDArray

from app.gemini import GeminiError, GeminiHttp

Matrix = NDArray[np.float32]


BATCH_SIZE = 100  # maximo de textos por chamada em batchEmbedContents

# Mantido por compatibilidade: erros de embedding sao erros do Gemini.
EmbeddingError = GeminiError


class Embedder(Protocol):
    """Contrato de quem gera embeddings: o real (Gemini) e o de reproducao (cassete)."""

    model: str
    dimensions: int

    def embed_documents(self, texts: Sequence[str]) -> Matrix: ...

    def embed_query(self, text: str) -> Matrix: ...


def normalize(matrix: Matrix) -> Matrix:
    """Deixa cada vetor com tamanho 1: assim cosseno = produto escalar."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class GeminiEmbedder:
    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int = 768,
        *,
        client: httpx.Client | None = None,
        max_retries: int = 4,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = GeminiHttp(api_key, client=client, max_retries=max_retries, sleep=sleep)
        self.model = model
        self.dimensions = dimensions

    def __repr__(self) -> str:
        return f"GeminiEmbedder(model={self.model!r}, dimensions={self.dimensions})"

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        """Textos da base (task RETRIEVAL_DOCUMENT)."""
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> Matrix:
        """Pergunta do usuario (task RETRIEVAL_QUERY); devolve matriz 1 x dimensoes."""
        return self._embed([text], "RETRIEVAL_QUERY")

    def _embed(self, texts: Sequence[str], task: str) -> Matrix:
        if not texts:
            return np.zeros((0, self.dimensions), dtype=np.float32)
        rows: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            payload = {
                "requests": [
                    {
                        "model": f"models/{self.model}",
                        "content": {"parts": [{"text": text}]},
                        "taskType": task,
                        "outputDimensionality": self.dimensions,
                    }
                    for text in batch
                ]
            }
            data = self._http.post(f"/models/{self.model}:batchEmbedContents", payload)
            embeddings = data.get("embeddings", [])
            if len(embeddings) != len(batch):
                raise EmbeddingError("Gemini devolveu quantidade de vetores diferente da enviada")
            rows.extend(item["values"] for item in embeddings)
        # Com dimensoes menores que o padrao a API nao normaliza; fazemos aqui.
        return normalize(np.array(rows, dtype=np.float32))


class EmbeddingCache:
    """Guarda vetores em disco, indexados por modelo + dimensoes + hash do texto."""

    def __init__(self, path: Path | None, data: dict[str, list[float]] | None = None) -> None:
        """`path=None` mantem tudo em memoria (usado na gravacao e na reproducao de cassetes)."""
        self._path = path
        self._data: dict[str, list[float]] = dict(data or {})
        if path is not None and path.is_file():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def key(model: str, dimensions: int, content_hash: str) -> str:
        return f"{model}|{dimensions}|{content_hash}"

    def get(self, key: str) -> list[float] | None:
        return self._data.get(key)

    def put(self, key: str, vector: list[float]) -> None:
        self._data[key] = vector

    def export(self) -> dict[str, list[float]]:
        return dict(self._data)

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data), encoding="utf-8")
        tmp.replace(self._path)  # troca atomica: nunca fica um arquivo pela metade
