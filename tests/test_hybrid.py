from app.ingest.chunking import Chunk
from app.retrieval.hit import Hit
from app.retrieval.hybrid import hybrid_search, is_confident, reciprocal_rank_fusion


def hit(name: str, score: float = 0.0) -> Hit:
    return Hit(Chunk(id=name, tenant="a", source="x", heading=name, body=name), score)


def test_confianca_exige_destaque_do_primeiro() -> None:
    assert is_confident([hit("A", 6.0), hit("B", 3.0)])  # 2x
    assert not is_confident([hit("A", 3.0), hit("B", 2.9)])  # empate: ruido
    assert is_confident([hit("A", 2.0)])  # unico que casou
    assert not is_confident([])


def test_bm25_confiante_e_concordante_entra_na_fusao() -> None:
    dense = [hit("X"), hit("Y"), hit("Z")]
    bm25 = [hit("Z", 9.0)]  # Z e o unico que casou e esta no top-3 do significado
    assert names(hybrid_search(dense, bm25))[0] == "Z"  # 1/63 + 1/61 > 1/61


def test_bm25_sem_destaque_nao_mexe_no_resultado() -> None:
    dense = [hit("X"), hit("Y"), hit("Z")]
    bm25 = [hit("Z", 3.0), hit("Y", 2.9)]
    assert names(hybrid_search(dense, bm25)) == ["X", "Y", "Z"]


def test_bm25_que_o_significado_desconhece_e_ignorado() -> None:
    dense = [hit(c) for c in "ABCDEFG"]
    bm25 = [hit("G", 9.0)]  # confiante, mas fora do top-5 do significado
    assert names(hybrid_search(dense, bm25)) == ["A", "B", "C"]
    # sem a exigencia de concordancia ele entraria (e arrastaria o G para cima):
    assert "G" in names(hybrid_search(dense, bm25, agree_within=None))


def test_sem_resultado_de_bm25_vale_o_significado() -> None:
    assert names(hybrid_search([hit("A"), hit("B")], [])) == ["A", "B"]


def names(hits: list[Hit]) -> list[str]:
    return [h.chunk.heading for h in hits]


def test_quem_aparece_bem_nas_duas_listas_sobe() -> None:
    significado = [hit("A"), hit("B"), hit("C")]
    palavras = [hit("D"), hit("B"), hit("E")]
    # B e 2o nas duas; A e D sao 1o em uma so.
    assert names(reciprocal_rank_fusion([significado, palavras]))[0] == "B"


def test_nao_repete_chunk_e_respeita_o_top() -> None:
    fused = reciprocal_rank_fusion([[hit("A"), hit("B")], [hit("A"), hit("C")]], top=2)
    assert names(fused) == ["A", "B"]
    assert len({h.chunk.id for h in fused}) == len(fused)


def test_so_a_posicao_conta_nao_a_pontuacao() -> None:
    alto = Hit(hit("A").chunk, 9999.0)
    baixo = Hit(hit("A").chunk, 0.001)
    assert reciprocal_rank_fusion([[alto]])[0].score == reciprocal_rank_fusion([[baixo]])[0].score


def test_uma_lista_vazia_nao_atrapalha_a_outra() -> None:
    assert names(reciprocal_rank_fusion([[], [hit("A"), hit("B")]])) == ["A", "B"]
    assert reciprocal_rank_fusion([[], []]) == []
