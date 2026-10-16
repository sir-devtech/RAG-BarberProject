"""Demonstracao OFFLINE: reproduz respostas gravadas do assistente. Sem chave e sem internet.

Uso: python -m scripts.demo

Roda o mesmo codigo da avaliacao (busca, ferramenta, regras e checagem de numeros) sobre as
respostas do Gemini gravadas no cassete. Para perguntar de verdade, use `scripts/ask.py` com a
sua propria chave. A sequencia foi escolhida para mostrar, nesta ordem: uma resposta com conta,
uma que corrige premissa falsa, duas recusas, duas manipulacoes e uma falha conhecida.
"""

from __future__ import annotations

import sys
import textwrap

from eval.answer_cases import TUNING_FILE, VALIDATION_FILE, CaseResult, load_cases
from eval.run_answers import replay

# (id do caso, o que esta cena demonstra)
DEMO: list[tuple[str, str]] = [
    ("t02", "Conta feita por codigo (ferramenta), nao pelo modelo"),
    ("t04", "Resposta simples, com a fonte citada"),
    ("t10", "Premissa falsa do cliente: o assistente corrige, nao confirma"),
    ("v11", "Outra premissa falsa"),
    ("t12", "Pergunta fora do assunto: recusa barata, sem chamar o modelo"),
    ("t14", "Pergunta vizinha sem resposta na base: o modelo recusa"),
    ("t15", "Tentativa de manipulacao"),
    ("v17", "Manipulacao para confirmar um preco falso"),
    ("v20", "FALHA CONHECIDA: a busca nao trouxe o trecho certo (ver caderno 07)"),
]
DEMO_IDS = [case_id for case_id, _ in DEMO]
WIDTH = 78


def load_demo_results() -> dict[str, CaseResult]:
    cases = {c.id: c for path in (TUNING_FILE, VALIDATION_FILE) for c in load_cases(path)}
    results = replay([cases[i] for i in DEMO_IDS])
    return {r.case.id: r for r in results}


def render(case_id: str, note: str, result: CaseResult, number: int, total: int) -> str:
    answer = result.answer
    verdict = "RESPONDEU" if answer.grounded else "RECUSOU"
    lines = [
        "=" * WIDTH,
        f"[{number}/{total}] {note}",
        "-" * WIDTH,
        f"PERGUNTA : {result.case.question}",
        f"{verdict:<9}: " + textwrap.fill(answer.text, WIDTH - 12, subsequent_indent=" " * 12),
    ]
    for source in answer.sources:
        lines.append(f"FONTE    : {source.source}  >  {source.heading.split(' > ')[-1]}")
    lines.append(f"MOTIVO   : {answer.reason}")
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    results = load_demo_results()
    print("Assistente do Sir Barber | demonstracao offline (respostas gravadas)\n")
    for number, (case_id, note) in enumerate(DEMO, start=1):
        print(render(case_id, note, results[case_id], number, len(DEMO)))
        print()
    print("=" * WIDTH)
    print('Para perguntar de verdade: python -m scripts.ask "sua pergunta" (usa a sua chave)')


if __name__ == "__main__":
    main()
