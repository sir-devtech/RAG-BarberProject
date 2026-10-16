"""Servico que a API chama: junta recuperacao, ferramentas e modelo."""

from __future__ import annotations

from typing import Protocol

import httpx

from app.api.lru import LruQueryEmbedder
from app.api.settings import ApiSettings
from app.config import Settings
from app.gemini import GeminiHttp
from app.generation.answer import Answer, answer_question
from app.generation.chat import GeminiChat
from app.ingest.embeddings import EmbeddingCache, GeminiEmbedder
from app.ingest.index import embed_chunks
from app.ingest.loader import load_tenant_chunks
from app.retrieval.bm25 import Bm25Index
from app.retrieval.dense import DenseIndex
from app.retrieval.retriever import Retriever
from app.tools.plans import PlansTool, load_plans

HTTP_TIMEOUT = 12.0  # segundos por tentativa
REQUEST_DEADLINE = 25.0  # segundos para o pedido inteiro, somando as tentativas


class AssistantService(Protocol):
    chunk_count: int

    def ask(self, question: str, tenant: str) -> Answer: ...


class RagService:
    def __init__(
        self, retriever: Retriever, chat: GeminiChat, tools: PlansTool, chunk_count: int
    ) -> None:
        self._retriever = retriever
        self._chat = chat
        self._tools = tools
        self.chunk_count = chunk_count

    def ask(self, question: str, tenant: str) -> Answer:
        return answer_question(question, tenant, self._retriever, self._chat, tools=self._tools)


def build_rag_service(settings: Settings, api: ApiSettings) -> RagService:
    """Carrega a base, gera (ou le do cache) os vetores e monta o recuperador."""
    chunks = [c for tenant in api.allowed_tenants for c in load_tenant_chunks(tenant)]
    # Na subida (uma vez, sem usuario esperando) vale esperar mais; nos pedidos, nao.
    startup = GeminiEmbedder(settings.gemini_api_key, settings.embedding_model)
    cache = EmbeddingCache(api.index_dir / "embeddings.json")
    dense = DenseIndex(chunks, embed_chunks(chunks, startup, cache))
    per_request = {"max_retries": 3, "max_total_seconds": REQUEST_DEADLINE}
    queries = GeminiEmbedder(
        settings.gemini_api_key,
        settings.embedding_model,
        client=httpx.Client(timeout=HTTP_TIMEOUT),
        **per_request,  # type: ignore[arg-type]
    )
    retriever = Retriever(
        dense,
        Bm25Index(chunks),
        LruQueryEmbedder(queries),  # vetores de perguntas: memoria com teto
        EmbeddingCache(None),
        cache_queries=False,  # numa API publica o cache de perguntas nao pode crescer sem limite
    )
    chat = GeminiChat(
        settings.gemini_api_key,
        settings.chat_model,
        http=GeminiHttp(
            settings.gemini_api_key,
            client=httpx.Client(timeout=HTTP_TIMEOUT),
            **per_request,  # type: ignore[arg-type]
        ),
    )
    return RagService(retriever, chat, PlansTool(load_plans()), len(chunks))
