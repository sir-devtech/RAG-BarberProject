"""Cliente de embeddings do Gemini, com retentativa e cache por hash do texto.

Embedding = lista de numeros que representa o SIGNIFICADO de um texto. Textos de sentido
parecido ficam com vetores proximos, mesmo sem palavras em comum.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import httpx
import numpy as np
from numpy.typing import NDArray

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
RETRY_STATUS = {429, 500, 502, 503, 504}  # limite de cota ou servidor sobrecarregado
BATCH_SIZE = 100  # maximo de textos por chamada em batchEmbedContents

Matrix = NDArray[np.float32]


class EmbeddingError(RuntimeError):
    """Falha ao gerar embeddings (a mensagem nunca contem a chave)."""


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
        self._api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self._client = client or httpx.Client(timeout=30.0)
        self._max_retries = max_retries
        self._sleep = sleep

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
            data = self._post(f"/models/{self.model}:batchEmbedContents", payload)
            embeddings = data.get("embeddings", [])
            if len(embeddings) != len(batch):
                raise EmbeddingError("Gemini devolveu quantidade de vetores diferente da enviada")
            rows.extend(item["values"] for item in embeddings)
        # Com dimensoes menores que o padrao a API nao normaliza; fazemos aqui.
        return normalize(np.array(rows, dtype=np.float32))

    def _post(
        self, path: str, payload: Mapping[str, object]
    ) -> dict[str, list[dict[str, list[float]]]]:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post(
                    f"{API_BASE}{path}",
                    json=payload,
                    headers={"x-goog-api-key": self._api_key},  # no cabecalho, nunca na URL
                )
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    nome = type(exc).__name__
                    raise EmbeddingError(f"Falha de rede ao chamar o Gemini: {nome}") from None
            else:
                if response.status_code == 200:
                    return response.json()  # type: ignore[no-any-return]
                if response.status_code not in RETRY_STATUS or attempt == self._max_retries:
                    detail = response.text.replace(self._api_key, "<chave>")[:200]
                    status = response.status_code
                    raise EmbeddingError(f"Gemini respondeu HTTP {status}: {detail}")
            self._sleep(2.0**attempt)  # 1s, 2s, 4s, 8s
        raise EmbeddingError("Tentativas esgotadas")  # inalcancavel; satisfaz o mypy


class EmbeddingCache:
    """Guarda vetores em disco, indexados por modelo + dimensoes + hash do texto."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, list[float]] = {}
        if path.is_file():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def key(model: str, dimensions: int, content_hash: str) -> str:
        return f"{model}|{dimensions}|{content_hash}"

    def get(self, key: str) -> list[float] | None:
        return self._data.get(key)

    def put(self, key: str, vector: list[float]) -> None:
        self._data[key] = vector

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data), encoding="utf-8")
        tmp.replace(self._path)  # troca atomica: nunca fica um arquivo pela metade
