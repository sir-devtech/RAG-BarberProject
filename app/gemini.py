"""Cliente HTTP do Gemini compartilhado por embeddings e chat: retentativa e chave protegida."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
RETRY_STATUS = {429, 500, 502, 503, 504}  # limite de cota ou servidor sobrecarregado


class GeminiError(RuntimeError):
    """Falha ao chamar o Gemini (a mensagem nunca contem a chave)."""


class GeminiHttp:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        max_retries: int = 4,
        sleep: Callable[[float], None] = time.sleep,
        max_total_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=60.0)
        self._max_retries = max_retries
        self._sleep = sleep
        # Prazo total de UM pedido (todas as tentativas). Sem ele, 4 tentativas de 60 s
        # prenderiam uma thread por minutos: numa API publica isso e uma forma de derruba-la.
        self._max_total = max_total_seconds
        self._clock = clock

    def __repr__(self) -> str:
        return "GeminiHttp()"

    def post(self, path: str, payload: Mapping[str, object]) -> dict[str, Any]:
        """POST com espera crescente (1, 2, 4, 8 s) so para erros temporarios."""
        started = self._clock()
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
                    raise GeminiError(f"Falha de rede ao chamar o Gemini: {nome}") from None
            else:
                if response.status_code == 200:
                    data: dict[str, Any] = response.json()
                    return data
                if response.status_code not in RETRY_STATUS or attempt == self._max_retries:
                    detail = response.text.replace(self._api_key, "<chave>")[:200]
                    status = response.status_code
                    raise GeminiError(f"Gemini respondeu HTTP {status}: {detail}")
            wait = 2.0**attempt  # 1s, 2s, 4s, 8s
            if self._max_total is not None and self._clock() - started + wait > self._max_total:
                raise GeminiError("Tempo limite esgotado ao chamar o Gemini")
            self._sleep(wait)
        raise GeminiError("Tentativas esgotadas")  # inalcancavel; satisfaz o mypy
