"""Configuracao lida do ambiente. Nenhum valor secreto fica no codigo."""

from __future__ import annotations

import os
from dataclasses import dataclass


class MissingSettingError(RuntimeError):
    """Variavel de ambiente obrigatoria ausente."""


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    chat_model: str
    embedding_model: str

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
