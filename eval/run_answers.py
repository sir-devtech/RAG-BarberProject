"""Avalia as RESPOSTAS do assistente (nao so a busca), nos conjuntos de ajuste e validacao.

Uso:
  python -m eval.run_answers                 # reproduz o cassete: offline, sem chave
  python -m eval.run_answers --record        # grava o cassete chamando a API de verdade
  python -m eval.run_answers --set validation --verbose
O modo --record grava e em seguida reproduz, para que a nota venha sempre do mesmo caminho.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from app.config import Settings
from app.generation.answer import answer_question
from app.generation.chat import GeminiChat
from app.ingest.embeddings import Embedder, EmbeddingCache, GeminiEmbedder
from app.ingest.index import embed_chunks
from app.ingest.loader import load_tenant_chunks
from app.retrieval.bm25 import Bm25Index
from app.retrieval.dense import DenseIndex
from app.retrieval.retriever import Retriever
from app.tools.plans import PlansTool, load_plans
from eval.answer_cases import (
    TUNING_FILE,
    VALIDATION_FILE,
    Case,
    CaseResult,
    Summary,
    grade,
    load_cases,
    summarize,
)
from eval.cassette import (
    CASSETTE_FILE,
    Cassette,
    RecordingChat,
    ReplayChat,
    ReplayEmbedder,
    RoundingEmbedder,
)

SETS = {"tuning": TUNING_FILE, "validation": VALIDATION_FILE}


def run_cases(
    cases: list[Case],
    embedder: Embedder,
    cache: EmbeddingCache,
    chat: object,
    *,
    pause: float = 0.0,
) -> list[CaseResult]:
    tenants = sorted({c.tenant for c in cases})
    chunks = [chunk for tenant in tenants for chunk in load_tenant_chunks(tenant)]
    dense = DenseIndex(chunks, embed_chunks(chunks, embedder, cache))
    retriever = Retriever(dense, Bm25Index(chunks), embedder, cache)
    tools = PlansTool(load_plans())
    results = []
    for case in cases:
        answer = answer_question(case.question, case.tenant, retriever, chat, tools=tools)  # type: ignore[arg-type]
        results.append(CaseResult(case, answer, grade(case, answer)))
        time.sleep(pause)
    return results


def record(cases: list[Case], pause: float) -> None:
    settings = Settings.load()
    live = GeminiEmbedder(settings.gemini_api_key, settings.embedding_model)
    embedder = RoundingEmbedder(live)
    cassette = Cassette(settings.embedding_model, embedder.dimensions)
    cache = EmbeddingCache(None)  # vazio e em memoria: so o que for usado fica gravado
    chat = RecordingChat(GeminiChat(settings.gemini_api_key, settings.chat_model), cassette.chat)
    run_cases(cases, embedder, cache, chat, pause=pause)
    cassette.embeddings = cache.export()
    cassette.save()
    size_kb = CASSETTE_FILE.stat().st_size // 1024
    print(
        f"Cassete gravado: {len(cassette.embeddings)} vetores, "
        f"{len(cassette.chat)} respostas, {size_kb} KB"
    )


def replay(cases: list[Case], path: Path = CASSETTE_FILE) -> list[CaseResult]:
    cassette = Cassette.load(path)
    embedder = ReplayEmbedder(cassette.model, cassette.dimensions)
    cache = EmbeddingCache(None, cassette.embeddings)
    return run_cases(cases, embedder, cache, ReplayChat(cassette.chat))


def print_summary(name: str, summary: Summary) -> None:
    pct = summary.passed / summary.total
    print(f"\n[{name}] {summary.passed}/{summary.total} aprovados ({pct:.0%})")
    print(f"  recusou quando devia responder : {summary.false_refusals}")
    print(f"  respondeu quando devia recusar : {summary.false_answers}")
    print(f"  resposta sem o conteudo certo  : {summary.wrong_content}")
    print(f"  numeros sem base nas fontes    : {summary.uncited_numbers}")
    print(f"  respostas que precisaram de correcao de numero: {summary.corrected}")
    print("  por tipo: " + " | ".join(f"{k} {a}/{t}" for k, (a, t) in summary.by_kind.items()))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="grava o cassete com a API real")
    parser.add_argument("--set", choices=[*SETS, "all"], default="all")
    parser.add_argument("--verbose", action="store_true", help="mostra cada caso reprovado")
    parser.add_argument("--pause", type=float, default=1.5, help="segundos entre perguntas")
    args = parser.parse_args()

    if args.record:
        every = [case for path in SETS.values() for case in load_cases(path)]
        record(every, args.pause)

    for name, path in SETS.items():
        if args.set not in (name, "all"):
            continue
        results = replay(load_cases(path))
        print_summary(name, summarize(results))
        if args.verbose:
            for r in results:
                if not r.passed:
                    print(f"\n  FALHOU {r.case.id} [{r.case.kind}] {r.case.question}")
                    print(f"    problemas: {r.problems}")
                    print(f"    resposta ({r.answer.reason}): {r.answer.text}")


if __name__ == "__main__":
    main()
