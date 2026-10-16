"""Compara a busca por significado, por palavras exatas e a hibrida no conjunto de perguntas.

Uso: python -m eval.run_eval [--verbose] [--sweep] [--ratio 1.5]
Precisa do .env (as perguntas sao embutidas na API; os vetores ficam em cache).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from app.config import Settings
from app.ingest.embeddings import EmbeddingCache, GeminiEmbedder
from app.ingest.index import cached_query_vector, embed_chunks
from app.ingest.loader import load_tenant_chunks
from app.retrieval.bm25 import Bm25Index
from app.retrieval.dense import DenseIndex
from app.retrieval.hit import Hit
from app.retrieval.hybrid import AGREE_WITHIN, CONFIDENCE_RATIO, hybrid_search
from eval.metrics import first_relevant_position, score_rankings

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval" / "dataset.jsonl"
CACHE_FILE = ROOT / ".index" / "embeddings.json"
POOL = 10  # quantos candidatos cada busca entrega para a fusao


def load_dataset(path: Path = DATASET) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="mostra pergunta a pergunta")
    parser.add_argument("--sweep", action="store_true", help="varia o criterio de confianca")
    parser.add_argument("--ratio", type=float, default=CONFIDENCE_RATIO)
    args = parser.parse_args()

    settings = Settings.load()
    embedder = GeminiEmbedder(settings.gemini_api_key, settings.embedding_model)
    cache = EmbeddingCache(CACHE_FILE)
    dataset = load_dataset()
    tenants = sorted({str(row["tenant"]) for row in dataset})
    chunks = [c for tenant in tenants for c in load_tenant_chunks(tenant)]
    dense = DenseIndex(chunks, embed_chunks(chunks, embedder, cache))
    bm25 = Bm25Index(chunks)

    def run_dense(question: str, tenant: str, pool: int = 3) -> list[Hit]:
        vector = cached_query_vector(embedder, cache, question)
        return dense.search(vector, tenant=tenant, k=pool)

    def run_bm25(question: str, tenant: str, pool: int = 3) -> list[Hit]:
        return bm25.search(question, tenant=tenant, k=pool)

    def run_hybrid(
        question: str,
        tenant: str,
        ratio: float = args.ratio,
        agree_within: int | None = AGREE_WITHIN,
    ) -> list[Hit]:
        return hybrid_search(
            run_dense(question, tenant, POOL),
            run_bm25(question, tenant, POOL),
            ratio=ratio,
            agree_within=agree_within,
        )

    questions = [(str(r["question"]), str(r["tenant"])) for r in dataset]
    relevants = [[str(h) for h in r["relevant"]] for r in dataset]  # type: ignore[attr-defined]
    paraphrases = [i for i, r in enumerate(dataset) if "parafrase" in str(r.get("note"))]

    systems: dict[str, Callable[[str, str], list[Hit]]] = {
        "significado": run_dense,
        "palavras": run_bm25,
        "hibrida": run_hybrid,
    }
    results: dict[str, list[list[str]]] = {
        name: [[h.chunk.heading for h in system(q, t)] for q, t in questions]
        for name, system in systems.items()
    }

    print(f"{len(dataset)} perguntas ({len(paraphrases)} parafrases) | {len(chunks)} chunks")
    print(f"modelo {settings.embedding_model} | criterio de confianca {args.ratio}\n")
    print(f"{'busca':<12}{'acerto@1':>10}{'acerto@3':>10}{'MRR':>8}   {'parafrases @1 / @3'}")
    for name, ranked in results.items():
        s = score_rankings(ranked, relevants)
        p = score_rankings([ranked[i] for i in paraphrases], [relevants[i] for i in paraphrases])
        print(
            f"{name:<12}{s.recall_at_1:>10.0%}{s.recall_at_3:>10.0%}{s.mrr:>8.2f}"
            f"   {p.recall_at_1:>8.0%} / {p.recall_at_3:.0%}"
        )

    if args.sweep:
        variants: dict[str, tuple[float, int | None]] = {
            "sempre funde (RRF puro)": (0.0, None),
            "so confianca (>= 1,5x)": (1.5, None),
            "confianca + concordancia top-5": (1.5, 5),
            "confianca + concordancia top-8": (1.5, 8),
        }
        print("\nRegras de fusao (a de significado sozinha esta na tabela acima):")
        print(f"{'regra':<34}{'@1':>6}{'@3':>6}{'MRR':>7}   {'parafrases @1 / @3'}")
        for label, (ratio, agree) in variants.items():
            rows = [[h.chunk.heading for h in run_hybrid(q, t, ratio, agree)] for q, t in questions]
            s = score_rankings(rows, relevants)
            p = score_rankings([rows[i] for i in paraphrases], [relevants[i] for i in paraphrases])
            print(
                f"{label:<34}{s.recall_at_1:>6.0%}{s.recall_at_3:>6.0%}{s.mrr:>7.2f}"
                f"   {p.recall_at_1:>8.0%} / {p.recall_at_3:.0%}"
            )

    if args.verbose:
        print("\nPosicao do primeiro chunk correto (- = nao veio nos 3 primeiros):")
        print(f"{'':<54}" + "".join(f"{n:>13}" for n in results))
        for i, (question, _) in enumerate(questions):
            cells = ""
            for ranked in results.values():
                position = first_relevant_position(ranked[i], relevants[i])
                cells += f"{position if position else '-':>13}"
            print(f"{question[:52]:<54}{cells}")
    cache.save()


if __name__ == "__main__":
    main()
