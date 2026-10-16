import numpy as np
import pytest

from app.ingest.chunking import Chunk
from app.retrieval.dense import DenseIndex


def chunk(tenant: str, heading: str) -> Chunk:
    return Chunk(id=heading, tenant=tenant, source=f"{tenant}/x.md", heading=heading, body="x")


# Vetores 2D ja normalizados: eixo X = "preco", eixo Y = "cancelamento".
PRECO = [1.0, 0.0]
CANCELAR = [0.0, 1.0]
MEIO = [0.7071, 0.7071]


def index() -> DenseIndex:
    chunks = [chunk("a", "preco-a"), chunk("a", "cancelar-a"), chunk("b", "preco-b")]
    return DenseIndex(chunks, np.array([PRECO, CANCELAR, PRECO], dtype=np.float32))


def query(vector: list[float]) -> np.ndarray:  # type: ignore[type-arg]
    return np.array([vector], dtype=np.float32)


def test_ordena_pelo_mais_parecido() -> None:
    hits = index().search(query(MEIO), tenant="a", k=2)
    assert [h.chunk.heading for h in hits][0] in {"preco-a", "cancelar-a"}
    top = index().search(query(PRECO), tenant="a", k=2)
    assert [h.chunk.heading for h in top] == ["preco-a", "cancelar-a"]
    assert top[0].score == pytest.approx(1.0)
    assert top[1].score == pytest.approx(0.0)


def test_isolamento_nunca_devolve_chunk_de_outra_loja() -> None:
    # preco-b e IDENTICO a pergunta, mas pertence a loja b.
    hits = index().search(query(PRECO), tenant="a", k=10)
    assert all(h.chunk.tenant == "a" for h in hits)
    assert "preco-b" not in [h.chunk.heading for h in hits]


def test_loja_sem_chunks_devolve_vazio() -> None:
    assert index().search(query(PRECO), tenant="inexistente") == []


def test_limiar_descarta_resultados_fracos() -> None:
    hits = index().search(query(PRECO), tenant="a", k=5, min_score=0.5)
    assert [h.chunk.heading for h in hits] == ["preco-a"]


def test_exige_um_vetor_por_chunk() -> None:
    with pytest.raises(ValueError):
        DenseIndex([chunk("a", "x")], np.zeros((2, 2), dtype=np.float32))
