"""Pergunta ao assistente (busca hibrida + Gemini). Usa a chave do .env.

Uso: python -m scripts.ask "quanto custa para 3 barbeiros?" ["outra pergunta" ...]
Opcoes: --tenant platform  --debug (mostra os trechos entregues ao modelo)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import Settings
from app.generation.answer import answer_question
from app.generation.chat import GeminiChat
from app.ingest.embeddings import EmbeddingCache, GeminiEmbedder
from app.ingest.index import embed_chunks
from app.ingest.loader import load_tenant_chunks
from app.retrieval.bm25 import Bm25Index
from app.retrieval.dense import DenseIndex
from app.retrieval.retriever import Retriever

CACHE_FILE = Path(__file__).resolve().parents[1] / ".index" / "embeddings.json"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", nargs="+")
    parser.add_argument("--tenant", default="platform")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    settings = Settings.load()
    embedder = GeminiEmbedder(settings.gemini_api_key, settings.embedding_model)
    cache = EmbeddingCache(CACHE_FILE)
    chunks = load_tenant_chunks(args.tenant)
    dense = DenseIndex(chunks, embed_chunks(chunks, embedder, cache))
    retriever = Retriever(dense, Bm25Index(chunks), embedder, cache)
    chat = GeminiChat(settings.gemini_api_key, settings.chat_model)

    for question in args.questions:
        print(f"\nPERGUNTA: {question}")
        if args.debug:
            found = retriever.retrieve(question, args.tenant)
            print(f"  [melhor similaridade: {found.best_similarity:.3f}]")
            for number, hit in enumerate(found.hits, start=1):
                print(f"  [trecho {number}] {hit.chunk.heading}")
        result = answer_question(question, args.tenant, retriever, chat)
        print(f"RESPOSTA ({result.reason}): {result.text}")
        for source in result.sources:
            print(f"  fonte [{source.number}] {source.source} > {source.heading}")
    cache.save()


if __name__ == "__main__":
    main()
