"""Metricas de busca. `ranked` e a lista de trilhas de titulo devolvida, em ordem."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Scores:
    recall_at_1: float  # fracao de perguntas com um chunk correto em 1o lugar
    recall_at_3: float  # ... entre os 3 primeiros
    mrr: float  # media de 1/posicao do primeiro chunk correto (0 se nao veio)


def first_relevant_position(ranked: Sequence[str], relevant: Sequence[str]) -> int | None:
    for position, heading in enumerate(ranked, start=1):
        if heading in relevant:
            return position
    return None


def score_rankings(
    rankings: Sequence[Sequence[str]], relevants: Sequence[Sequence[str]]
) -> Scores:
    if len(rankings) != len(relevants) or not rankings:
        raise ValueError("Precisa de um ranking e um gabarito por pergunta")
    positions = [
        first_relevant_position(r, rel) for r, rel in zip(rankings, relevants, strict=True)
    ]
    total = len(positions)
    return Scores(
        recall_at_1=sum(p == 1 for p in positions) / total,
        recall_at_3=sum(p is not None and p <= 3 for p in positions) / total,
        mrr=sum(1 / p for p in positions if p) / total,
    )
