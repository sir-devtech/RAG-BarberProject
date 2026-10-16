import json

import httpx
import numpy as np
import pytest

from app.ingest.chunking import Chunk
from app.ingest.embeddings import (
    BATCH_SIZE,
    EmbeddingCache,
    EmbeddingError,
    GeminiEmbedder,
    normalize,
)
from app.ingest.index import embed_chunks

SEGREDO = "chave-secreta-de-teste"


def fake_vector(text: str) -> list[float]:
    return [float(len(text)), 1.0, 0.0, 2.0]


class FakeGemini:
    """Servidor simulado: responde conforme o roteiro de status e registra as chamadas."""

    def __init__(self, statuses: list[int] | None = None) -> None:
        self.statuses = statuses or []
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.statuses:
            status = self.statuses.pop(0)
            if status != 200:
                return httpx.Response(status, text=f"erro {SEGREDO}")
        body = json.loads(request.content)
        texts = [r["content"]["parts"][0]["text"] for r in body["requests"]]
        items = [{"values": fake_vector(text)} for text in texts]
        return httpx.Response(200, json={"embeddings": items})


def embedder(server: FakeGemini, sleeps: list[float] | None = None) -> GeminiEmbedder:
    return GeminiEmbedder(
        SEGREDO,
        "modelo-teste",
        client=httpx.Client(transport=httpx.MockTransport(server)),
        sleep=(sleeps if sleeps is not None else []).append,
    )


def test_normalize_deixa_vetores_com_tamanho_1() -> None:
    out = normalize(np.array([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32))
    assert np.allclose(np.linalg.norm(out[0]), 1.0)
    assert np.allclose(out[1], 0.0)  # vetor nulo nao vira NaN


def test_envia_chave_no_cabecalho_e_tarefa_correta() -> None:
    server = FakeGemini()
    out = embedder(server).embed_documents(["abc", "de"])
    request = server.requests[0]
    assert request.headers["x-goog-api-key"] == SEGREDO
    assert SEGREDO not in str(request.url)
    sent = json.loads(request.content)["requests"][0]
    assert sent["taskType"] == "RETRIEVAL_DOCUMENT"
    assert sent["outputDimensionality"] == 768
    assert out.shape == (2, 4)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)


def test_pergunta_usa_tarefa_de_consulta() -> None:
    server = FakeGemini()
    embedder(server).embed_query("quanto custa?")
    assert json.loads(server.requests[0].content)["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_tenta_de_novo_em_503_com_espera_crescente() -> None:
    server, sleeps = FakeGemini([503, 503, 200]), []
    out = embedder(server, sleeps).embed_documents(["abc"])
    assert out.shape == (1, 4)
    assert len(server.requests) == 3
    assert sleeps == [1.0, 2.0]


def test_desiste_depois_das_tentativas_sem_vazar_a_chave() -> None:
    server = FakeGemini([503] * 10)
    with pytest.raises(EmbeddingError) as err:
        embedder(server).embed_documents(["abc"])
    assert "503" in str(err.value)
    assert SEGREDO not in str(err.value)
    assert len(server.requests) == 5  # 1 + 4 tentativas


def test_erro_do_cliente_nao_e_repetido() -> None:
    server = FakeGemini([400])
    with pytest.raises(EmbeddingError):
        embedder(server).embed_documents(["abc"])
    assert len(server.requests) == 1


def test_divide_em_lotes_de_100() -> None:
    server = FakeGemini()
    out = embedder(server).embed_documents([f"texto {i}" for i in range(BATCH_SIZE + 5)])
    assert len(server.requests) == 2
    assert out.shape[0] == BATCH_SIZE + 5


def make_chunk(body: str) -> Chunk:
    return Chunk(id="x", tenant="loja-a", source="loja-a/x.md", heading="T", body=body)


def test_cache_so_chama_a_api_para_texto_novo_ou_alterado(tmp_path) -> None:  # type: ignore[no-untyped-def]
    server = FakeGemini()
    cache_file = tmp_path / "cache.json"
    emb = embedder(server)
    chunks = [make_chunk("um"), make_chunk("dois")]

    embed_chunks(chunks, emb, EmbeddingCache(cache_file))
    assert len(server.requests) == 1

    embed_chunks(chunks, emb, EmbeddingCache(cache_file))  # tudo no cache
    assert len(server.requests) == 1

    embed_chunks([make_chunk("um"), make_chunk("dois mudou")], emb, EmbeddingCache(cache_file))
    assert len(server.requests) == 2
    enviados = json.loads(server.requests[1].content)["requests"]
    assert [r["content"]["parts"][0]["text"] for r in enviados] == ["T\ndois mudou"]
