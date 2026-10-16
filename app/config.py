"""Configuracao lida do ambiente. Nenhum valor secreto fica no codigo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class MissingSettingError(RuntimeError):
    """Variavel de ambiente obrigatoria ausente."""


def read_env_file(path: Path) -> dict[str, str]:
    """Le um arquivo .env simples (NOME=valor). Linhas vazias e # sao ignoradas."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    chat_model: str
    embedding_model: str

    @classmethod
    def load(cls, env_file: Path = ENV_FILE) -> Settings:
        """Arquivo .env primeiro; variaveis do ambiente (ex.: servidor, CI) tem prioridade."""
        return cls.from_env({**read_env_file(env_file), **os.environ})

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        values = {
            "GEMINI_API_KEY": source.get("GEMINI_API_KEY", "").strip(),
            "GEMINI_CHAT_MODEL": source.get("GEMINI_CHAT_MODEL", "").strip(),
            "GEMINI_EMBEDDING_MODEL": source.get("GEMINI_EMBEDDING_MODEL", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            # Lista so os NOMES faltando, nunca os valores.
            raise MissingSettingError(f"Defina no .env: {', '.join(missing)}")
        return cls(
            gemini_api_key=values["GEMINI_API_KEY"],
            chat_model=values["GEMINI_CHAT_MODEL"],
            embedding_model=values["GEMINI_EMBEDDING_MODEL"],
        )

    def __repr__(self) -> str:
        # Evita vazar a chave em logs/tracebacks.
        return f"Settings(chat_model={self.chat_model!r}, embedding_model={self.embedding_model!r})"
