"""Defesas na entrada: tamanho do corpo e cabecalhos de seguranca."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"cache-control", b"no-store"),
    (b"referrer-policy", b"no-referrer"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
]


class BodyLimitMiddleware:
    """Recusa corpos acima de `max_bytes`, inclusive os enviados em pedacos (chunked).

    So olhar o cabecalho Content-Length nao basta: quem envia em pedacos nao o declara.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(send)
            return

        received = 0
        too_large = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    too_large = True
                    return {"type": "http.disconnect"}  # manda o app parar de ler
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if too_large:
                return  # o FastAPI responderia 400 ao ver a leitura cortada; a resposta e nossa
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not too_large:
                raise
        if too_large and not started:
            await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = json.dumps({"erro": "Pedido grande demais"}).encode()
        headers = [(b"content-type", b"application/json"), *SECURITY_HEADERS]
        headers.append((b"content-length", str(len(body)).encode()))
        await send({"type": "http.response.start", "status": 413, "headers": headers})
        await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    """Cabecalhos que uma API de JSON nao precisa abrir mao: nada de cache, sniffing ou iframe."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def add_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name for name, _ in message["headers"]}
                message["headers"] = [
                    *message["headers"],
                    *[(n, v) for n, v in SECURITY_HEADERS if n not in present],
                ]
            await send(message)

        await self.app(scope, receive, add_headers)
