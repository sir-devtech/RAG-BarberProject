"""Checagem de fidelidade: todo numero da resposta precisa existir no contexto ou na pergunta.

E feita por CODIGO, depois do modelo, porque pedir "nao invente" no prompt nao garante nada.
Limite conhecido: numeros escritos por extenso ("tres") nao sao checados.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

# 1.250,90 | 1.250 | 250,50 | 250. O ponto so e milhar quando seguido de exatamente 3 digitos.
NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _parse(token: str) -> Decimal | None:
    try:
        return Decimal(token.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def numbers_in(text: str) -> dict[Decimal, str]:
    """Numeros do texto, como valor (250,00 == 250) -> primeira grafia encontrada."""
    found: dict[Decimal, str] = {}
    for token in NUMBER.findall(text):
        value = _parse(token)
        if value is not None:
            found.setdefault(value, token)
    return found


MONEY = re.compile(rf"R\$\s*({NUMBER.pattern})")


def _money_values(text: str) -> set[Decimal]:
    return {v for token in MONEY.findall(text) if (v := _parse(token)) is not None}


def ungrounded_numbers(
    answer: str, context_texts: Iterable[str], echoable_texts: Iterable[str] = ()
) -> list[str]:
    """Numeros da resposta que nao tem base no contexto.

    `context_texts`: o que os trechos dizem. Todo numero da resposta pode vir daqui.
    `echoable_texts`: normalmente a pergunta. Seus numeros so podem ser repetidos quando NAO
    sao dinheiro ("para 5 barbeiros"). Um valor em R$ nunca e aceito so porque o cliente o
    mencionou: senao "o plano custa R$ 99, certo?" faria o modelo confirmar R$ 99.
    """
    context: set[Decimal] = set()
    for text in context_texts:
        context.update(numbers_in(text))
    echoable: set[Decimal] = set()
    for text in echoable_texts:
        echoable.update(numbers_in(text))
    money = _money_values(answer)
    invented: list[str] = []
    for value, token in numbers_in(answer).items():
        allowed = context if value in money else context | echoable
        if value not in allowed:
            invented.append(token)
    return invented
