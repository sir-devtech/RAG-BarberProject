"""Divide documentos markdown em pedacos (chunks) prontos para busca.

Ideia central: cada chunk carrega a TRILHA DE TITULOS ("Planos > Simples Pequena").
Sem ela, um pedaco como "custa R$ 160 por mes" perde o contexto e a busca nao sabe
a que plano o valor pertence.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
# Fim de frase ou quebra de linha (cobre listas, que quase nao tem ponto final).
FALLBACK_SPLIT = re.compile(r"(?<=[.!?])\s+|\n")
MIN_CHUNK_CHARS = 100


@dataclass(frozen=True)
class Chunk:
    id: str
    tenant: str
    source: str
    heading: str
    body: str

    @property
    def text(self) -> str:
        """Texto que vai para o embedding: trilha de titulos + conteudo."""
        return f"{self.heading}\n{self.body}" if self.heading else self.body

    @property
    def content_hash(self) -> str:
        """Muda so quando o texto muda; permite reaproveitar embeddings ja gerados."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


def _sections(markdown: str) -> list[tuple[str, str]]:
    """Quebra o documento em (trilha de titulos, corpo). Secoes sem corpo sao descartadas."""
    trail: list[str] = []
    heading = ""
    lines: list[str] = []
    found: list[tuple[str, str]] = []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if body:
            found.append((heading, body))
        lines.clear()

    for line in markdown.splitlines():
        match = HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            trail = [*trail[: level - 1], match.group(2)]
            heading = " > ".join(trail)
        else:
            lines.append(line)
    flush()
    return found


def _units(body: str, max_chars: int) -> list[str]:
    """Unidades atomicas da secao: paragrafos; os grandes demais viram frases/linhas."""
    units: list[str] = []
    for paragraph in PARAGRAPH_BREAK.split(body):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            units.append(paragraph)
        else:
            units.extend(part.strip() for part in FALLBACK_SPLIT.split(paragraph) if part.strip())
    return units


def _pack(units: list[str], max_chars: int, overlap_units: int) -> list[list[str]]:
    """Agrupa unidades vizinhas sem passar de max_chars (uma unidade gigante fica sozinha).

    Ao abrir um grupo novo, ele ja comeca repetindo as ultimas `overlap_units` unidades do
    anterior (so se couberem junto com a proxima unidade). Assim o overlap nunca estoura o
    limite e nao e "tentado so no final", quando o grupo ja estaria cheio.
    """
    groups: list[list[str]] = []
    current: list[str] = []
    size = 0
    for unit in units:
        extra = len(unit) + (1 if current else 0)
        if current and size + extra > max_chars:
            groups.append(current)
            seed = current[-overlap_units:] if overlap_units > 0 else []
            seed_size = len("\n".join(seed))
            if seed and seed_size + 1 + len(unit) <= max_chars:
                current, size = list(seed), seed_size
            else:
                current, size = [], 0
            extra = len(unit) + (1 if current else 0)
        current.append(unit)
        size += extra
    if current:
        groups.append(current)
    return groups


def chunk_markdown(
    markdown: str,
    *,
    tenant: str,
    source: str,
    max_chars: int = 600,
    overlap_units: int = 1,
) -> list[Chunk]:
    """Transforma um markdown em chunks.

    max_chars: tamanho maximo do corpo de cada chunk (a trilha de titulos vai a mais).
    overlap_units: quantas unidades finais do chunk anterior se repetem no proximo,
        quando uma secao precisa ser dividida (so se couberem dentro de max_chars).
    """
    if max_chars < MIN_CHUNK_CHARS:
        raise ValueError(f"max_chars deve ser >= {MIN_CHUNK_CHARS}")
    chunks: list[Chunk] = []
    for heading, body in _sections(markdown):
        for group in _pack(_units(body, max_chars), max_chars, overlap_units):
            digest = hashlib.sha256(f"{tenant}|{source}|{len(chunks)}".encode()).hexdigest()
            chunks.append(
                Chunk(
                    id=digest[:12],
                    tenant=tenant,
                    source=source,
                    heading=heading,
                    body="\n".join(group),
                )
            )
    return chunks
