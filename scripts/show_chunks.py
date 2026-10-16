"""Mostra como a base de uma loja foi dividida em chunks.

Uso: python -m scripts.show_chunks platform [--max-chars 600]
"""

from __future__ import annotations

import argparse
import sys

from app.ingest.loader import load_tenant_chunks


def main() -> None:
    # O console do Windows nem sempre e UTF-8; sem isso os acentos saem quebrados.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant")
    parser.add_argument("--max-chars", type=int, default=600)
    args = parser.parse_args()

    chunks = load_tenant_chunks(args.tenant, max_chars=args.max_chars)
    for number, chunk in enumerate(chunks, start=1):
        print(f"--- [{number}/{len(chunks)}] {chunk.source} | {len(chunk.body)} caracteres")
        print(f"    trilha: {chunk.heading}")
        print(chunk.body)
        print()
    sizes = [len(c.body) for c in chunks]
    print(f"{len(chunks)} chunks | menor {min(sizes)} | maior {max(sizes)}", end="")
    print(f" | limite {args.max_chars}")


if __name__ == "__main__":
    main()
