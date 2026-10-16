"""Responde uma pergunta: recupera, decide se ha base suficiente e so entao chama o modelo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.generation.fidelity import ungrounded_numbers
from app.generation.prompts import RESPONSE_SCHEMA, SYSTEM_PROMPT, build_user_prompt
from app.retrieval.hit import Hit
from app.retrieval.retriever import Retrieval

# Cosseno minimo da melhor busca por significado para valer a pena chamar o modelo.
# Calibrado em docs/aprendizado/05 com perguntas dentro e fora do escopo.
MIN_SIMILARITY = 0.60
MAX_QUESTION_CHARS = 500
REFUSAL = "Não encontrei essa informação. Fale com a equipe do Sir Barber para confirmar."


class RetrieverLike(Protocol):
    def retrieve(self, question: str, tenant: str, *, top: int = 3) -> Retrieval: ...


class ToolRouter(Protocol):
    def hits(self, question: str, tenant: str) -> list[Hit]: ...


class ChatLike(Protocol):
    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Source:
    number: int
    source: str
    heading: str


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[Source]
    grounded: bool  # True so quando a resposta veio do modelo, com fonte valida
    # ok | sem_contexto | baixa_similaridade | modelo_insuficiente | sem_fonte
    # | numero_nao_fundamentado
    reason: str


def refuse(reason: str) -> Answer:
    return Answer(text=REFUSAL, sources=[], grounded=False, reason=reason)


def _valid_sources(raw: object, hits: list[Hit]) -> list[Source]:
    """Aceita so numeros de trechos que realmente foram entregues ao modelo."""
    numbers = raw if isinstance(raw, list) else []
    chosen: list[Source] = []
    for number in dict.fromkeys(n for n in numbers if isinstance(n, int)):
        if 1 <= number <= len(hits):
            chunk = hits[number - 1].chunk
            chosen.append(Source(number, chunk.source, chunk.heading))
    return chosen


def _correction_note(numbers: list[str]) -> str:
    lista = ", ".join(numbers)
    return (
        "\n\nATENÇÃO: sua resposta anterior citou valores que NÃO estão nos trechos: "
        f"{lista}. Responda de novo usando apenas números escritos nos trechos, "
        "ou marque suficiente=false."
    )


def answer_question(
    question: str,
    tenant: str,
    retriever: RetrieverLike,
    chat: ChatLike,
    *,
    tools: ToolRouter | None = None,
    min_similarity: float = MIN_SIMILARITY,
    top: int = 3,
) -> Answer:
    question = question.strip()
    if not question or len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"A pergunta deve ter entre 1 e {MAX_QUESTION_CHARS} caracteres")

    retrieval = retriever.retrieve(question, tenant, top=top)
    tool_hits = tools.hits(question, tenant) if tools else []
    hits = [*tool_hits, *retrieval.hits]  # o resultado da ferramenta vem primeiro
    if not hits:
        return refuse("sem_contexto")
    # A ferramenta so dispara em pergunta do dominio, entao ela dispensa o limiar.
    if not tool_hits and retrieval.best_similarity < min_similarity:
        return refuse("baixa_similaridade")  # nem chama o modelo: nao ha o que ele ancorar

    prompt = build_user_prompt(question, hits)
    context = [hit.chunk.text for hit in hits]
    result = chat.generate_json(SYSTEM_PROMPT, prompt, RESPONSE_SCHEMA)
    for attempt in range(2):  # 1a resposta + no maximo 1 correcao
        if result.get("suficiente") is not True:
            return refuse("modelo_insuficiente")
        text = str(result.get("resposta", "")).strip()
        sources = _valid_sources(result.get("fontes"), hits)
        if not text or not sources:
            return refuse("sem_fonte")  # resposta sem fonte valida nao e confiavel
        invented = ungrounded_numbers(text, context, [question])
        if not invented:
            return Answer(text=text, sources=sources, grounded=True, reason="ok")
        if attempt == 0:
            result = chat.generate_json(
                SYSTEM_PROMPT, prompt + _correction_note(invented), RESPONSE_SCHEMA
            )
    return refuse("numero_nao_fundamentado")
