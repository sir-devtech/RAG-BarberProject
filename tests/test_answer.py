from typing import Any

import pytest

from app.generation.answer import MAX_QUESTION_CHARS, REFUSAL, answer_question
from app.ingest.chunking import Chunk
from app.retrieval.hit import Hit
from app.retrieval.retriever import Retrieval


def hit(heading: str, body: str = "corpo") -> Hit:
    chunk = Chunk(id=heading, tenant="a", source="a/x.md", heading=heading, body=body)
    return Hit(chunk, 0.0)


class FakeRetriever:
    def __init__(self, hits: list[Hit], best: float = 0.9) -> None:
        self._retrieval = Retrieval(hits=hits, best_similarity=best)
        self.calls = 0

    def retrieve(self, question: str, tenant: str, *, top: int = 3) -> Retrieval:
        self.calls += 1
        return self._retrieval


class FakeChat:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls = 0
        self.user_prompts: list[str] = []

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        self.user_prompts.append(user)
        return self.result


OK = {"suficiente": True, "resposta": "Custa R$ 160.", "fontes": [1]}


def test_resposta_com_fonte_valida() -> None:
    chat = FakeChat(OK)
    retriever = FakeRetriever([hit("Planos > Pequena", "O plano custa R$ 160 por mês.")])
    result = answer_question("quanto custa?", "a", retriever, chat)
    assert result.grounded and result.reason == "ok"
    assert result.text == "Custa R$ 160."
    assert [(s.number, s.heading) for s in result.sources] == [(1, "Planos > Pequena")]


def test_similaridade_baixa_nem_chama_o_modelo() -> None:
    chat = FakeChat(OK)
    result = answer_question("capital da franca?", "a", FakeRetriever([hit("X")], best=0.51), chat)
    assert (result.grounded, result.reason, result.text) == (False, "baixa_similaridade", REFUSAL)
    assert chat.calls == 0


def test_sem_trechos_nem_chama_o_modelo() -> None:
    chat = FakeChat(OK)
    assert answer_question("oi?", "a", FakeRetriever([]), chat).reason == "sem_contexto"
    assert chat.calls == 0


def test_modelo_diz_que_nao_e_suficiente() -> None:
    chat = FakeChat({"suficiente": False, "resposta": "chute", "fontes": [1]})
    result = answer_question("quanto custa um corte?", "a", FakeRetriever([hit("X")]), chat)
    assert (result.grounded, result.reason, result.text) == (False, "modelo_insuficiente", REFUSAL)


def test_resposta_sem_fonte_valida_e_descartada() -> None:
    for fontes in ([], [7], [0], ["1"], None):
        chat = FakeChat({"suficiente": True, "resposta": "Custa R$ 1.", "fontes": fontes})
        result = answer_question("q?", "a", FakeRetriever([hit("X")]), chat)
        assert result.reason == "sem_fonte", fontes
        assert not result.grounded


def test_fontes_repetidas_e_invalidas_sao_filtradas() -> None:
    chat = FakeChat({"suficiente": True, "resposta": "ok", "fontes": [2, 2, 9, 1]})
    result = answer_question("q?", "a", FakeRetriever([hit("A"), hit("B")]), chat)
    assert [s.heading for s in result.sources] == ["B", "A"]


def test_suficiente_precisa_ser_exatamente_true() -> None:
    for value in ("true", 1, None):
        chat = FakeChat({"suficiente": value, "resposta": "ok", "fontes": [1]})
        assert answer_question("q?", "a", FakeRetriever([hit("A")]), chat).reason == (
            "modelo_insuficiente"
        )


def test_pergunta_invalida() -> None:
    for question in ["", "   ", "x" * (MAX_QUESTION_CHARS + 1)]:
        with pytest.raises(ValueError):
            answer_question(question, "a", FakeRetriever([hit("A")]), FakeChat(OK))


def test_o_modelo_so_recebe_os_trechos_da_recuperacao() -> None:
    chat = FakeChat(OK)
    answer_question("q?", "a", FakeRetriever([hit("So Esta")]), chat)
    assert "So Esta" in chat.user_prompts[0]


class SequenceChat:
    """Devolve uma resposta diferente a cada chamada (para testar a correcao)."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.prompts: list[str] = []

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(user)
        return self.results[min(len(self.prompts) - 1, len(self.results) - 1)]


def resposta(texto: str) -> dict[str, Any]:
    return {"suficiente": True, "resposta": texto, "fontes": [1]}


TEXTO = "O plano Simples Pequena custa R$ 160 por mês, de 2 a 3 barbeiros."
BASE = [hit("Planos > Pequena", TEXTO)]


def test_numero_inventado_ganha_uma_correcao_e_entao_passa() -> None:
    chat = SequenceChat([resposta("Custa R$ 199 por mês."), resposta("Custa R$ 160 por mês.")])
    result = answer_question("quanto custa?", "a", FakeRetriever(BASE), chat)
    assert result.grounded and result.text == "Custa R$ 160 por mês."
    assert len(chat.prompts) == 2
    assert "199" in chat.prompts[1] and "NÃO estão nos trechos" in chat.prompts[1]


def test_numero_inventado_que_persiste_vira_recusa() -> None:
    chat = SequenceChat([resposta("Custa R$ 199.")])
    result = answer_question("quanto custa?", "a", FakeRetriever(BASE), chat)
    assert (result.grounded, result.reason) == (False, "numero_nao_fundamentado")
    assert len(chat.prompts) == 2  # nunca mais de uma correcao


def test_numeros_da_propria_pergunta_sao_permitidos() -> None:
    chat = SequenceChat([resposta("Para 3 barbeiros, custa R$ 160 por mês.")])
    result = answer_question("quanto custa para 3 barbeiros?", "a", FakeRetriever(BASE), chat)
    assert result.grounded
    assert len(chat.prompts) == 1


def test_formatos_de_dinheiro_equivalentes_sao_aceitos() -> None:
    chat = SequenceChat([resposta("Custa R$ 160,00 por mês.")])
    assert answer_question("q?", "a", FakeRetriever(BASE), chat).grounded


def test_ferramenta_entra_como_primeiro_trecho_e_dispensa_o_limiar() -> None:
    chunk = Chunk(
        id="t", tenant="a", source="ferramenta:planos", heading="Ferr", body="R$ 250 por mês"
    )
    chat = SequenceChat([resposta("Custa R$ 250 por mês.")])

    class Tools:
        def hits(self, question: str, tenant: str) -> list[Hit]:
            return [Hit(chunk, 1.0)]

    result = answer_question(
        "quanto custa?", "a", FakeRetriever([hit("X")], best=0.10), chat, tools=Tools()
    )
    assert result.grounded
    assert result.sources[0].source == "ferramenta:planos"
    assert chat.prompts[0].index("Ferr") < chat.prompts[0].index('secao="X"')


def test_modelo_nao_pode_confirmar_preco_falso_dito_pelo_cliente() -> None:
    base = [hit("Planos > Solo", "O plano Simples Solo custa R$ 120 por mês.")]
    chat = SequenceChat([resposta("Sim, o plano Solo custa R$ 99.")])
    result = answer_question("o plano Solo custa R$ 99, certo?", "a", FakeRetriever(base), chat)
    assert (result.grounded, result.reason) == (False, "numero_nao_fundamentado")
