from app.ingest.chunking import Chunk
from app.retrieval.bm25 import Bm25Index


def chunk(tenant: str, heading: str, body: str) -> Chunk:
    return Chunk(id=f"{tenant}-{heading}", tenant=tenant, source="x", heading=heading, body=body)


BASE = [
    chunk("a", "Planos > Solo", "O plano Solo custa R$ 120 por mes para 1 barbeiro."),
    chunk("a", "Planos > Media", "O plano Media custa R$ 250 por mes para ate 8 barbeiros."),
    chunk("a", "Planos > Grande", "O plano Grande custa R$ 350 por mes para ate 12 barbeiros."),
    chunk("a", "Regras > Cancelar", "Pode cancelar quando quiser, sem multa."),
    chunk("b", "Planos > Outra loja", "O plano especial custa R$ 250 por mes e tem desconto."),
]


def test_valor_exato_acha_so_o_chunk_que_o_contem() -> None:
    hits = Bm25Index(BASE).search("R$ 250", tenant="a")
    assert [h.chunk.heading for h in hits] == ["Planos > Media"]


def test_palavra_rara_pesa_mais_que_palavra_comum() -> None:
    hits = Bm25Index(BASE).search("plano cancelar", tenant="a", k=4)
    assert hits[0].chunk.heading == "Regras > Cancelar"  # "plano" esta em 3 chunks; "cancelar" em 1


def test_sem_palavra_em_comum_nao_devolve_nada() -> None:
    assert Bm25Index(BASE).search("helicoptero", tenant="a") == []


def test_isolamento_nunca_devolve_chunk_de_outra_loja() -> None:
    hits = Bm25Index(BASE).search("R$ 250 desconto especial", tenant="a", k=10)
    assert all(h.chunk.tenant == "a" for h in hits)
    assert Bm25Index(BASE).search("R$ 250", tenant="b")[0].chunk.heading == "Planos > Outra loja"


def test_estatisticas_de_uma_loja_nao_mudam_com_outra_loja() -> None:
    so_a = Bm25Index([c for c in BASE if c.tenant == "a"]).search("R$ 250", tenant="a")
    com_b = Bm25Index(BASE).search("R$ 250", tenant="a")
    assert so_a[0].score == com_b[0].score  # IDF calculado so com os chunks da propria loja


def test_loja_inexistente_devolve_vazio() -> None:
    assert Bm25Index(BASE).search("plano", tenant="zzz") == []


def test_chunk_curto_ganha_do_longo_com_a_mesma_palavra() -> None:
    curto = chunk("a", "Curto", "multa")
    longo = chunk("a", "Longo", "multa " + " ".join(f"palavra{i}" for i in range(40)))
    hits = Bm25Index([curto, longo]).search("multa", tenant="a")
    assert hits[0].chunk.heading == "Curto"
