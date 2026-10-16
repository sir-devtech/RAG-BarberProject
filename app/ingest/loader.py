"""Le a base de conhecimento (knowledge/<loja>/*.md) e devolve os chunks de uma loja."""

from __future__ import annotations

import re
from pathlib import Path

from app.ingest.chunking import Chunk, chunk_markdown

TENANT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"


def load_tenant_chunks(
    tenant: str,
    *,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
    max_chars: int = 600,
) -> list[Chunk]:
    # O slug vira nome de pasta: validar impede "../" e leitura de outras pastas.
    if not TENANT_SLUG.fullmatch(tenant):
        raise ValueError(f"Loja invalida: {tenant!r}")
    folder = knowledge_dir / tenant
    if not folder.is_dir():
        raise FileNotFoundError(f"Sem base de conhecimento para a loja {tenant!r}")
    chunks: list[Chunk] = []
    for path in sorted(folder.glob("*.md")):
        chunks.extend(
            chunk_markdown(
                path.read_text(encoding="utf-8"),
                tenant=tenant,
                source=f"{tenant}/{path.name}",
                max_chars=max_chars,
            )
        )
    return chunks
