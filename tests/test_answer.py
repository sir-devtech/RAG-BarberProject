from typing import Any

import pytest

from app.generation.answer import MAX_QUESTION_CHARS, REFUSAL, answer_question
from app.ingest.chunking import Chunk
from app.retrieval.hit import Hit
from app.retrieval.retriever import Retrieval


def hit(heading: str) -> Hit:
    chunk = Chunk(id=heading, tenant="a", source="a/x.md", heading=heading, body="corpo")
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
    result = answer_question("quanto custa?", "a", FakeRetriever([hit("Planos > Pequena")]), chat)
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
