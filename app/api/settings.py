"""Configuracao da API, lida do ambiente. Valor invalido derruba a subida (falha cedo)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from app.config import ENV_FILE, read_env_file

TENANT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,40}$")
ROOT = Path(__file__).resolve().parents[2]


class ApiSettingsError(ValueError):
    """Configuracao invalida da API."""


def _positive(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiSettingsError(f"{name} deve ser um numero inteiro") from None
    if value < 1:
        raise ApiSettingsError(f"{name} deve ser >= 1")
    return value


def _csv(env: Mapping[str, str], name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env.get(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class ApiSettings:
    allowed_tenants: list[str] = field(default_factory=lambda: ["platform"])
    cors_origins: list[str] = field(default_factory=list)  # vazio = nenhum site de fora
    client_ip_header: str | None = None  # ex.: CF-Connecting-IP; None = IP do socket
    per_minute: int = 6
    per_day: int = 60
    daily_cap: int = 400
    max_body_bytes: int = 4096
    metrics_token: str | None = None  # sem token, /metrics nem existe
    enable_docs: bool = False
    index_dir: Path = ROOT / ".index"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ApiSettings:
        source = env if env is not None else {**read_env_file(ENV_FILE), **os.environ}
        tenants = _csv(source, "ALLOWED_TENANTS", "platform")
        for tenant in tenants:
            if not TENANT_SLUG.fullmatch(tenant):
                raise ApiSettingsError(f"Loja invalida em ALLOWED_TENANTS: {tenant!r}")
        origins = _csv(source, "CORS_ORIGINS")
        for origin in origins:
            if origin == "*" or not origin.startswith(("https://", "http://localhost")):
                raise ApiSettingsError(f"Origem CORS insegura ou invalida: {origin!r}")
        header = source.get("CLIENT_IP_HEADER", "").strip() or None
        if header and not HEADER_NAME.fullmatch(header):
            raise ApiSettingsError("CLIENT_IP_HEADER invalido")
        bearer = source.get("METRICS_TOKEN", "").strip() or None
        if bearer is not None and len(bearer) < 16:
            raise ApiSettingsError("METRICS_TOKEN deve ter pelo menos 16 caracteres")
        return cls(
            allowed_tenants=tenants,
            cors_origins=origins,
            client_ip_header=header,
            per_minute=_positive(source, "RATE_PER_MINUTE", 6),
            per_day=_positive(source, "RATE_PER_DAY", 60),
            daily_cap=_positive(source, "DAILY_CAP", 400),
            max_body_bytes=_positive(source, "MAX_BODY_BYTES", 4096),
            metrics_token=bearer,
            enable_docs=source.get("ENABLE_DOCS", "").strip().lower() in {"1", "true", "sim"},
            index_dir=Path(source.get("INDEX_DIR", "").strip() or str(ROOT / ".index")),
        )
