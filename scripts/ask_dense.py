"""Faz perguntas a base usando SO a busca por significado (embeddings).

Uso: python -m scripts.ask_dense "quanto custa para 3 barbeiros?" "posso desmarcar?"
Opcoes: --tenant platform  --k 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import Settings
from app.ingest.embeddings import EmbeddingCache, GeminiEmbedder
from app.ingest.index import embed_chunks
from app.ingest.loader import load_tenant_chunks
from app.retrieval.dense import DenseIndex

CACHE_FILE = Path(__file__).resolve().parents[1] / ".index" / "embeddings.json"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", nargs="+")
    parser.add_argument("--tenant", default="platform")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    settings = Settings.load()
    embedder = GeminiEmbedder(settings.gemini_api_key, settings.embedding_model)
    chunks = load_tenant_chunks(args.tenant)
    index = DenseIndex(chunks, embed_chunks(chunks, embedder, EmbeddingCache(CACHE_FILE)))

    for question in args.questions:
        print(f"\nPERGUNTA: {question}")
        query = embedder.embed_query(question)
        for rank, hit in enumerate(index.search(query, tenant=args.tenant, k=args.k), 1):
            first_line = hit.chunk.body.splitlines()[0][:90]
            print(f"  {rank}. {hit.score:.3f}  {hit.chunk.heading}")
            print(f"           {first_line}")


if __name__ == "__main__":
    main()
