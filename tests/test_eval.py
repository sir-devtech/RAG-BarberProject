import pytest

from app.ingest.loader import load_tenant_chunks
from eval.metrics import first_relevant_position, score_rankings
from eval.run_eval import load_dataset


def test_posicao_do_primeiro_correto() -> None:
    assert first_relevant_position(["x", "y", "z"], ["y", "z"]) == 2
    assert first_relevant_position(["x"], ["y"]) is None


def test_metricas() -> None:
    scores = score_rankings(
        [["ok", "x", "y"], ["x", "ok", "y"], ["x", "y", "z"], ["x", "y", "z", "ok"]],
        [["ok"], ["ok"], ["ok"], ["ok"]],
    )
    assert scores.recall_at_1 == 0.25
    assert scores.recall_at_3 == 0.5
    assert scores.mrr == pytest.approx((1 + 0.5 + 0 + 0.25) / 4)


def test_exige_um_gabarito_por_pergunta() -> None:
    with pytest.raises(ValueError):
        score_rankings([["a"]], [])


def test_conjunto_de_perguntas_so_aponta_para_chunks_que_existem() -> None:
    """Se alguem renomear um titulo na base, este teste avisa antes da avaliacao mentir."""
    existentes = {c.heading for c in load_tenant_chunks("platform")}
    for row in load_dataset():
        for heading in row["relevant"]:  # type: ignore[attr-defined]
            assert heading in existentes, f"gabarito desatualizado: {heading!r}"
