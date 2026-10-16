"""Ferramenta de planos: dado o numero de barbeiros, calcula quais planos servem.

"Quanto custa para 5 barbeiros?" exige uma conta (5 esta na faixa 4-8). Busca por texto nao
faz conta de forma confiavel; este codigo faz, e o resultado entra no contexto como um
trecho a mais, passando pela mesma checagem de numeros das demais fontes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.ingest.chunking import Chunk
from app.retrieval.hit import Hit
from app.retrieval.text import strip_accents

PLANS_FILE = Path(__file__).resolve().parents[2] / "knowledge" / "platform" / "plans.json"
MAX_BARBERS_PLANNED = 12  # acima disso nao ha plano publicado

NUMBER_WORDS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
}  # fmt: skip
STAFF = r"(?:barbeiros?|profissionais|funcionarios?|cadeiras?|colaboradores?)"
COUNT = re.compile(rf"\b(\d{{1,3}}|{'|'.join(NUMBER_WORDS)})\s+{STAFF}\b")


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price: int
    min_barbers: int
    max_barbers: int
    asaas: bool
    price_is_minimum: bool


def load_plans(path: Path = PLANS_FILE) -> list[Plan]:
    return [Plan(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


def plans_for(barbers: int, plans: Sequence[Plan]) -> list[Plan]:
    return [p for p in plans if p.min_barbers <= barbers <= p.max_barbers]


def extract_barber_count(question: str) -> int | None:
    """Acha 'N barbeiros' (digitos ou por extenso) na pergunta. None se nao houver."""
    match = COUNT.search(strip_accents(question).lower())
    if not match:
        return None
    raw = match.group(1)
    count = int(raw) if raw.isdigit() else NUMBER_WORDS[raw]
    return count if count >= 1 else None


def _line(plan: Plan) -> str:
    price = f"a partir de R$ {plan.price}" if plan.price_is_minimum else f"R$ {plan.price}"
    if plan.min_barbers == plan.max_barbers:
        faixa = f"{plan.min_barbers} barbeiro"
    else:
        faixa = f"{plan.min_barbers} a {plan.max_barbers} barbeiros"
    cobranca = "com" if plan.asaas else "sem"
    return f"- {plan.name}: {price} por mês, para {faixa}, {cobranca} cobrança Asaas."


def describe(barbers: int, plans: Sequence[Plan]) -> str:
    matches = plans_for(barbers, plans)
    if not matches:
        return (
            f"Nenhum plano publicado atende {barbers} barbeiros: "
            f"os planos vão até {MAX_BARBERS_PLANNED} barbeiros."
        )
    lines = "\n".join(_line(p) for p in matches)
    return f"Planos que atendem {barbers} barbeiros:\n{lines}"


class PlansTool:
    """Entrega o resultado do calculo como um trecho extra, so para a base da plataforma."""

    def __init__(self, plans: Sequence[Plan], *, tenants: Sequence[str] = ("platform",)) -> None:
        self._plans = list(plans)
        self._tenants = set(tenants)

    def hits(self, question: str, tenant: str) -> list[Hit]:
        count = extract_barber_count(question)
        if count is None or tenant not in self._tenants:
            return []
        chunk = Chunk(
            id=f"tool-plans-{count}",
            tenant=tenant,
            source="ferramenta:planos",
            heading=f"Ferramenta de planos > {count} barbeiros",
            body=describe(count, self._plans),
        )
        return [Hit(chunk, 1.0)]
