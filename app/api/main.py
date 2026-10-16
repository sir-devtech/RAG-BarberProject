"""API HTTP do assistente.

Ordem das defesas em POST /perguntar (a mais barata primeiro):
  tamanho do corpo -> limite por IP (antes de validar, para conter spam invalido tambem)
  -> validacao -> loja permitida -> teto diario -> modelo.
Erros internos nunca chegam ao cliente: so uma mensagem generica.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.limits import DailyCap, SlidingWindowLimiter
from app.api.metrics import Metrics
from app.api.middleware import BodyLimitMiddleware, SecurityHeadersMiddleware
from app.api.service import AssistantService, build_rag_service
from app.api.settings import TENANT_SLUG, ApiSettings
from app.config import Settings
from app.gemini import GeminiError
from app.generation.answer import MAX_QUESTION_CHARS

log = logging.getLogger("assistente")
Tenant = Annotated[str, StringConstraints(pattern=TENANT_SLUG.pattern)]


class Pergunta(BaseModel):
    model_config = ConfigDict(extra="forbid")  # campo desconhecido = erro, nao ignorado

    pergunta: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    loja: Tenant = "platform"


class FonteOut(BaseModel):
    numero: int
    arquivo: str
    secao: str


class Resposta(BaseModel):
    resposta: str
    fontes: list[FonteOut]
    respondeu: bool
    motivo: str


def hash_ip(ip: str, salt: str) -> str:
    """Identifica um cliente nos logs sem guardar o IP (o sal muda a cada reinicio)."""
    return hashlib.sha256(f"{salt}|{ip}".encode()).hexdigest()[:12]


def log_event(**fields: Any) -> None:
    log.info(json.dumps(fields, ensure_ascii=False, sort_keys=True))


def create_app(service: AssistantService, settings: ApiSettings | None = None) -> FastAPI:
    cfg = settings or ApiSettings()
    metrics = Metrics()
    per_minute = SlidingWindowLimiter(cfg.per_minute, 60)
    per_day = SlidingWindowLimiter(cfg.per_day, 86_400)
    cap = DailyCap(cfg.daily_cap)
    salt = secrets.token_hex(8)

    app = FastAPI(
        title="Assistente Sir Barber",
        docs_url="/docs" if cfg.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if cfg.enable_docs else None,
    )

    def client_ip(request: Request) -> str:
        if cfg.client_ip_header:
            forwarded = request.headers.get(cfg.client_ip_header, "").split(",")[0].strip()
            if forwarded:
                return forwarded
        return request.client.host if request.client else "desconhecido"

    def enforce_limits(request: Request) -> None:
        ip = client_ip(request)
        request.state.ip_hash = hash_ip(ip, salt)
        for limiter, scope in ((per_minute, "minuto"), (per_day, "dia")):
            allowed, wait = limiter.allow(ip)
            if not allowed:
                metrics.record(429, 0.0, f"limite_por_{scope}")
                log_event(evento="limite", ip=request.state.ip_hash, janela=scope)
                raise HTTPException(
                    429,
                    "Muitas perguntas. Tente novamente mais tarde.",
                    headers={"Retry-After": str(wait)},
                )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "trechos": service.chunk_count}

    @app.post("/perguntar", response_model=Resposta, dependencies=[Depends(enforce_limits)])
    def perguntar(body: Pergunta, request: Request) -> Resposta:
        started = time.perf_counter()
        ip = getattr(request.state, "ip_hash", "?")

        def done(status: int, reason: str) -> None:
            ms = (time.perf_counter() - started) * 1000
            metrics.record(status, ms, reason)
            # Nunca o texto da pergunta nem o IP: so o tamanho e um identificador com sal.
            log_event(
                evento="pergunta", ip=ip, loja=body.loja, status=status,
                motivo=reason, chars=len(body.pergunta), ms=round(ms),
            )  # fmt: skip

        if body.loja not in cfg.allowed_tenants:
            done(404, "loja_indisponivel")
            raise HTTPException(404, "Loja não disponível.")
        if not cap.take():
            done(503, "teto_diario")
            raise HTTPException(503, "Assistente indisponível hoje. Tente amanhã.")
        try:
            answer = service.ask(body.pergunta, body.loja)
        except GeminiError:
            done(503, "gemini_indisponivel")
            raise HTTPException(503, "Assistente temporariamente indisponível.") from None
        except Exception:
            log.exception("erro inesperado")  # o detalhe fica no log do servidor, nunca na resposta
            done(500, "erro_interno")
            raise HTTPException(500, "Erro interno.") from None
        done(200, answer.reason)
        return Resposta(
            resposta=answer.text,
            fontes=[
                FonteOut(numero=s.number, arquivo=s.source, secao=s.heading) for s in answer.sources
            ],
            respondeu=answer.grounded,
            motivo=answer.reason,
        )

    if cfg.metrics_token:
        expected = cfg.metrics_token

        @app.get("/metrics")
        def metrics_view(request: Request) -> dict[str, Any]:
            given = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not secrets.compare_digest(given.encode(), expected.encode()):  # tempo constante
                raise HTTPException(401, "Não autorizado.")
            return {**metrics.snapshot(), "teto_diario_usado": cap.used}

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"erro": exc.detail}, status_code=exc.status_code, headers=exc.headers)

    app.add_middleware(SecurityHeadersMiddleware)
    if cfg.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            max_age=600,
        )
    app.add_middleware(BodyLimitMiddleware, max_bytes=cfg.max_body_bytes)
    return app


def build_app() -> FastAPI:
    """Fabrica usada pelo servidor: uvicorn --factory app.api.main:build_app"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    api = ApiSettings.from_env()
    service = build_rag_service(Settings.load(), api)
    return create_app(service, api)
