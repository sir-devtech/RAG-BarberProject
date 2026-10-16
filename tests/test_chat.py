import json

import httpx
import pytest

from app.gemini import GeminiError, GeminiHttp
from app.generation.chat import GeminiChat

SEGREDO = "chave-secreta-de-teste"


def chat_with(parts: list[dict[str, object]], captured: list[httpx.Request]) -> GeminiChat:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": parts}}]})

    http = GeminiHttp(SEGREDO, client=httpx.Client(transport=httpx.MockTransport(handler)))
    return GeminiChat(SEGREDO, "modelo-teste", http=http)


def test_envia_instrucao_de_sistema_json_e_temperatura_zero() -> None:
    sent: list[httpx.Request] = []
    chat = chat_with([{"text": '{"suficiente": true}'}], sent)
    assert chat.generate_json("SISTEMA", "USUARIO", {"type": "OBJECT"}) == {"suficiente": True}
    body = json.loads(sent[0].content)
    assert body["systemInstruction"]["parts"][0]["text"] == "SISTEMA"
    assert body["contents"][0]["parts"][0]["text"] == "USUARIO"
    assert body["generationConfig"]["temperature"] == 0
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert sent[0].headers["x-goog-api-key"] == SEGREDO
    assert SEGREDO not in str(sent[0].url)


def test_ignora_partes_de_raciocinio_do_modelo() -> None:
    parts = [{"text": "pensando...", "thought": True}, {"text": '{"a": 1}'}]
    assert chat_with(parts, []).generate_json("s", "u", {}) == {"a": 1}


def test_json_invalido_vira_erro_claro() -> None:
    with pytest.raises(GeminiError):
        chat_with([{"text": "isto nao e json"}], []).generate_json("s", "u", {})


def test_resposta_que_nao_e_objeto_vira_erro() -> None:
    with pytest.raises(GeminiError):
        chat_with([{"text": "[1, 2]"}], []).generate_json("s", "u", {})


def test_resposta_sem_candidatos_vira_erro() -> None:
    http = GeminiHttp(
        SEGREDO,
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))),
    )
    with pytest.raises(GeminiError):
        GeminiChat(SEGREDO, "m", http=http).generate_json("s", "u", {})


def test_repr_nao_vaza_a_chave() -> None:
    assert SEGREDO not in repr(chat_with([], []))
