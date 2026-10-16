"""Cassete: grava as respostas da API uma vez e as reproduz offline (CI, sem chave).

Grava dois tipos de chamada:
- vetores de embedding (chunks e perguntas), indexados como no EmbeddingCache;
- saidas do chat, indexadas por um hash do prompt (sistema + usuario).

Se a base de conhecimento, o prompt ou as perguntas mudarem, a chave muda, o cassete "nao
tem" a gravacao e o teste falha pedindo para regravar: assim ninguem altera o assistente sem
reavaliar. O cassete so contem texto publico da base e vetores arredondados: nenhuma chave.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.ingest.embeddings import Embedder, Matrix

CASSETTE_FILE = Path(__file__).resolve().parent / "cassettes" / "answers.json"
VECTOR_DECIMALS = 4  # arredondar encolhe o arquivo; o cosseno quase nao muda


class CassetteMissError(RuntimeError):
    """A reproducao pediu algo que nao foi gravado."""


def chat_key(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\x00{user}".encode()).hexdigest()[:16]


@dataclass
class Cassette:
    model: str = ""
    dimensions: int = 0
    embeddings: dict[str, list[float]] = field(default_factory=dict)
    chat: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = CASSETTE_FILE) -> Cassette:
        if not path.is_file():
            raise CassetteMissError(
                f"Sem cassete em {path}. Rode: python -m eval.run_answers --record"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["model"], data["dimensions"], data["embeddings"], data["chat"])

    def save(self, path: Path = CASSETTE_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rounded = {
            key: [round(x, VECTOR_DECIMALS) for x in vec] for key, vec in self.embeddings.items()
        }
        payload = {
            "model": self.model,
            "dimensions": self.dimensions,
            "embeddings": rounded,
            "chat": self.chat,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), "utf-8")


class RoundingEmbedder:
    """Arredonda os vetores ja na gravacao, para gravar e reproduzir verem os MESMOS numeros.

    Sem isto, a gravacao usaria precisao total e a reproducao vetores arredondados; num
    empate de pontuacao a ordem dos trechos mudaria, o prompt mudaria e o cassete nao casaria.
    """

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self.model = inner.model
        self.dimensions = inner.dimensions

    def _round(self, matrix: Matrix) -> Matrix:
        return np.round(matrix, VECTOR_DECIMALS).astype(np.float32)

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        return self._round(self._inner.embed_documents(texts))

    def embed_query(self, text: str) -> Matrix:
        return self._round(self._inner.embed_query(text))


class ReplayEmbedder:
    """No lugar do Gemini: qualquer chamada significa que faltou gravar."""

    def __init__(self, model: str, dimensions: int) -> None:
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        raise CassetteMissError("Embedding de documento nao gravado. Regrave o cassete.")

    def embed_query(self, text: str) -> Matrix:
        raise CassetteMissError(f"Embedding da pergunta nao gravado ({text[:40]!r}). Regrave.")


class ReplayChat:
    def __init__(self, recorded: dict[str, dict[str, Any]]) -> None:
        self._recorded = recorded

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        found = self._recorded.get(chat_key(system, user))
        if found is None:
            raise CassetteMissError("Resposta do modelo nao gravada para este prompt. Regrave.")
        return dict(found)


class RecordingChat:
    """Envolve o chat real e guarda cada resposta no cassete."""

    def __init__(self, inner: Any, store: dict[str, dict[str, Any]]) -> None:
        self._inner = inner
        self._store = store

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = self._inner.generate_json(system, user, schema)
        self._store[chat_key(system, user)] = result
        return result
