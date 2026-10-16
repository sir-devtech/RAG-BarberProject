"""Responde uma pergunta: recupera, decide se ha base suficiente e so entao chama o modelo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

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
    reason: str  # ok | sem_contexto | baixa_similaridade | modelo_insuficiente | sem_fonte


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


def answer_question(
    question: str,
    tenant: str,
    retriever: RetrieverLike,
    chat: ChatLike,
    *,
    min_similarity: float = MIN_SIMILARITY,
    top: int = 3,
) -> Answer:
    question = question.strip()
    if not question or len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"A pergunta deve ter entre 1 e {MAX_QUESTION_CHARS} caracteres")

    retrieval = retriever.retrieve(question, tenant, top=top)
    if not retrieval.hits:
        return refuse("sem_contexto")
    if retrieval.best_similarity < min_similarity:
        return refuse("baixa_similaridade")  # nem chama o modelo: nao ha o que ele ancorar

    result = chat.generate_json(
        SYSTEM_PROMPT, build_user_prompt(question, retrieval.hits), RESPONSE_SCHEMA
    )
    if result.get("suficiente") is not True:
        return refuse("modelo_insuficiente")
    text = str(result.get("resposta", "")).strip()
    sources = _valid_sources(result.get("fontes"), retrieval.hits)
    if not text or not sources:
        return refuse("sem_fonte")  # resposta sem fonte valida nao e confiavel
    return Answer(text=text, sources=sources, grounded=True, reason="ok")
