"""Gate de qualidade: reproduz o cassete (sem rede/chave) e exige o piso de thresholds.json.

Se este teste falhar por "nao gravado", algo que afeta o prompt mudou (base de conhecimento,
prompt, regras de busca ou perguntas): regrave com `python -m eval.run_answers --record`,
leia o relatorio e so entao ajuste o piso, explicando no PR.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from app.generation.answer import Answer, Source
from eval.answer_cases import (
    TUNING_FILE,
    VALIDATION_FILE,
    Case,
    CaseResult,
    grade,
    load_cases,
    summarize,
)
from eval.cassette import (
    CASSETTE_FILE,
    Cassette,
    CassetteMissError,
    ReplayChat,
    RoundingEmbedder,
    chat_key,
)
from eval.run_answers import replay

THRESHOLDS = json.loads((Path(CASSETTE_FILE).parent.parent / "thresholds.json").read_text("utf-8"))


def ok_answer(text: str, source_text: str = "O plano custa R$ 160.") -> Answer:
    sources = [Source(1, "a/x.md", "Planos > Pequena", source_text)]
    return Answer(text=text, sources=sources, grounded=True, reason="ok")


def refusal(reason: str = "modelo_insuficiente") -> Answer:
    return Answer(text="Não encontrei.", sources=[], grounded=False, reason=reason)


def case(**kwargs: object) -> Case:
    base = {"id": "x", "kind": "in_scope", "question": "quanto custa?", "tenant": "a"}
    return Case(**{**base, "behavior": "answer", **kwargs})  # type: ignore[arg-type]


# ---------- gate sobre o cassete gravado ----------


SETS = [("tuning", TUNING_FILE), ("validation", VALIDATION_FILE)]


@pytest.mark.parametrize(("name", "path"), SETS)
def test_gate_de_qualidade_das_respostas(name: str, path: Path) -> None:
    summary = summarize(replay(load_cases(path)))
    floor = THRESHOLDS[name]
    assert summary.total == floor["of"], "o conjunto mudou: regrave e atualize thresholds.json"
    assert summary.passed >= floor["min_passed"], f"{name}: {summary.passed}/{summary.total}"
    assert summary.false_answers <= THRESHOLDS["max_false_answers"]
    assert summary.uncited_numbers <= THRESHOLDS["max_uncited_numbers"]


# ---------- correcao de um caso ----------


def test_correto_quando_responde_com_o_conteudo_esperado() -> None:
    assert grade(case(must_contain=["160"]), ok_answer("Custa R$ 160.")) == []


def test_recusar_quando_devia_responder_e_falha() -> None:
    assert "recusou" in grade(case(), refusal())[0]


def test_responder_quando_devia_recusar_e_falha() -> None:
    assert "respondeu quando devia recusar" in grade(case(behavior="refuse"), ok_answer("x"))[0]


def test_either_aceita_recusa_ou_resposta_correta_mas_nao_resposta_errada() -> None:
    manipulacao = case(behavior="either", must_contain=["650"])
    assert grade(manipulacao, refusal()) == []
    assert grade(manipulacao, ok_answer("Custa R$ 650.", "Premium: R$ 650")) == []
    assert grade(manipulacao, ok_answer("Custa R$ 1.", "Premium: R$ 650"))


def test_acentos_e_maiusculas_nao_atrapalham_a_conferencia() -> None:
    answer = ok_answer("O plano Completo inclui WhatsApp.", "WhatsApp")
    assert grade(case(must_contain=["COMPLETO", "whatsapp"]), answer) == []


def test_must_contain_any_exige_pelo_menos_um() -> None:
    assert grade(case(must_contain_any=["alfa", "beta"]), ok_answer("tem beta aqui", "beta")) == []
    assert grade(case(must_contain_any=["alfa", "beta"]), ok_answer("nada", "nada"))


def test_numero_sem_base_nas_fontes_citadas_e_apontado() -> None:
    """Checagem independente: mais estrita que a do pipeline, que olha todos os trechos."""
    problems = grade(case(), ok_answer("Custa R$ 199.", "O plano custa R$ 160."))
    assert any("sem base" in p for p in problems)


# ---------- resumo ----------


def test_resumo_conta_cada_tipo_de_erro() -> None:
    results = [
        CaseResult(case(id="a"), ok_answer("ok", "x"), []),
        CaseResult(case(id="b"), refusal(), ["recusou quando devia responder (x)"]),
        CaseResult(
            case(id="c", behavior="refuse"), ok_answer("x"), ["respondeu quando devia recusar"]
        ),
        CaseResult(case(id="d", kind="tool"), ok_answer("x"), ["falta '250'"]),
    ]
    s = summarize(results)
    assert (s.total, s.passed) == (4, 1)
    assert (s.false_refusals, s.false_answers, s.wrong_content) == (1, 1, 1)
    assert s.by_kind["in_scope"] == (1, 3) and s.by_kind["tool"] == (0, 1)


# ---------- casos e cassete ----------


def test_conjuntos_de_perguntas_sao_validos_e_nao_se_misturam() -> None:
    tuning, validation = load_cases(TUNING_FILE), load_cases(VALIDATION_FILE)
    assert not {c.id for c in tuning} & {c.id for c in validation}
    assert not {c.question for c in tuning} & {c.question for c in validation}, (
        "pergunta repetida entre ajuste e validacao contamina a validacao"
    )


def test_cassete_nao_tem_nada_que_pareca_chave() -> None:
    text = CASSETTE_FILE.read_text(encoding="utf-8")
    for padrao in ["AIza", "api_key", "API_KEY", "x-goog"]:
        assert padrao not in text


def test_reproducao_recusa_o_que_nao_foi_gravado() -> None:
    with pytest.raises(CassetteMissError):
        ReplayChat({}).generate_json("s", "u", {})


def test_chave_do_chat_depende_do_prompt_inteiro() -> None:
    assert chat_key("s", "u") == chat_key("s", "u")
    assert chat_key("s", "u") != chat_key("s", "u2")
    assert chat_key("s", "u") != chat_key("s2", "u")


def test_cassete_guarda_vetores_arredondados(tmp_path: Path) -> None:
    cassette = Cassette("m", 3, {"k": [0.123456, -0.987654, 0.5]}, {"h": {"a": 1}})
    cassette.save(tmp_path / "c.json")
    assert Cassette.load(tmp_path / "c.json").embeddings["k"] == [0.1235, -0.9877, 0.5]


def test_arredondar_na_gravacao_e_identico_ao_que_o_cassete_devolve() -> None:
    class Inner:
        model, dimensions = "m", 3

        def embed_documents(self, texts: object) -> np.ndarray:  # type: ignore[type-arg]
            return np.array([[0.123456, -0.987654, 0.5]], dtype=np.float32)

        def embed_query(self, text: str) -> np.ndarray:  # type: ignore[type-arg]
            return self.embed_documents([text])

    gravado = RoundingEmbedder(Inner()).embed_documents(["x"])[0].tolist()  # type: ignore[arg-type]
    guardado = [round(x, 4) for x in gravado]
    assert np.array(guardado, dtype=np.float32).tolist() == gravado
