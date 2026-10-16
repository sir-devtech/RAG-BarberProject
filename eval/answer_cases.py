"""Casos de avaliacao de respostas e a correcao de cada um."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.generation.answer import Answer
from app.generation.fidelity import ungrounded_numbers
from app.retrieval.text import strip_accents

EVAL_DIR = Path(__file__).resolve().parent
TUNING_FILE = EVAL_DIR / "answers_tuning.jsonl"
VALIDATION_FILE = EVAL_DIR / "answers_validation.jsonl"
BEHAVIORS = {"answer", "refuse", "either"}


@dataclass(frozen=True)
class Case:
    id: str
    kind: str  # in_scope | tool | false_premise | out_of_scope | injection
    question: str
    tenant: str
    behavior: str  # answer: deve responder | refuse: deve recusar | either: qualquer um, se correto
    must_contain: list[str] = field(default_factory=list)  # todos
    must_contain_any: list[str] = field(default_factory=list)  # pelo menos um


def load_cases(path: Path) -> list[Case]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if raw["behavior"] not in BEHAVIORS:
            raise ValueError(f"{raw['id']}: comportamento invalido {raw['behavior']!r}")
        cases.append(Case(**raw))
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"ids repetidos em {path.name}")
    return cases


def norm(text: str) -> str:
    return strip_accents(text).lower()


def content_problems(case: Case, answer: Answer) -> list[str]:
    text = norm(answer.text)
    problems = [f"falta {item!r}" for item in case.must_contain if norm(item) not in text]
    if case.must_contain_any and not any(norm(i) in text for i in case.must_contain_any):
        problems.append(f"falta um de {case.must_contain_any}")
    return problems


def grade(case: Case, answer: Answer) -> list[str]:
    """Lista de problemas. Vazia = caso aprovado."""
    problems: list[str] = []
    if case.behavior == "answer" and not answer.grounded:
        return [f"recusou quando devia responder ({answer.reason})"]
    if case.behavior == "refuse" and answer.grounded:
        return ["respondeu quando devia recusar"]
    if answer.grounded:
        problems.extend(content_problems(case, answer))
        # Checagem independente da do pipeline: so vale o que os trechos CITADOS dizem.
        cited = [source.text for source in answer.sources]
        invented = ungrounded_numbers(answer.text, cited, [case.question])
        if invented:
            problems.append(f"numeros sem base nas fontes citadas: {invented}")
    return problems


@dataclass(frozen=True)
class CaseResult:
    case: Case
    answer: Answer
    problems: list[str]

    @property
    def passed(self) -> bool:
        return not self.problems


@dataclass(frozen=True)
class Summary:
    total: int
    passed: int
    false_refusals: int  # devia responder e recusou
    false_answers: int  # devia recusar e respondeu
    wrong_content: int  # respondeu, mas faltou o conteudo esperado
    uncited_numbers: int  # numeros sem base nas fontes citadas
    corrected: int  # respostas em que o modelo precisou corrigir numeros inventados
    by_kind: dict[str, tuple[int, int]]  # tipo -> (aprovados, total)


def summarize(results: Sequence[CaseResult]) -> Summary:
    by_kind: Counter[str] = Counter()
    kind_total: Counter[str] = Counter()
    for r in results:
        kind_total[r.case.kind] += 1
        by_kind[r.case.kind] += r.passed
    return Summary(
        total=len(results),
        passed=sum(r.passed for r in results),
        false_refusals=sum(any("recusou" in p for p in r.problems) for r in results),
        false_answers=sum(any("respondeu quando" in p for p in r.problems) for r in results),
        wrong_content=sum(any(p.startswith("falta") for p in r.problems) for r in results),
        uncited_numbers=sum(any("sem base" in p for p in r.problems) for r in results),
        corrected=sum(r.answer.corrections > 0 for r in results),
        by_kind={k: (by_kind[k], kind_total[k]) for k in sorted(kind_total)},
    )
