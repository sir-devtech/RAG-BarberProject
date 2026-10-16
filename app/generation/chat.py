"""Cliente de chat do Gemini com saida em JSON."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.gemini import GeminiError, GeminiHttp


class GeminiChat:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: httpx.Client | None = None,
        http: GeminiHttp | None = None,
    ) -> None:
        self._http = http or GeminiHttp(api_key, client=client)
        self.model = model

    def __repr__(self) -> str:
        return f"GeminiChat(model={self.model!r})"

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0,  # mesma pergunta, mesma resposta: mais facil de testar
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        data = self._http.post(f"/models/{self.model}:generateContent", payload)
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p["text"] for p in parts if not p.get("thought") and "text" in p)
            result = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise GeminiError("Resposta do Gemini fora do formato esperado") from None
        if not isinstance(result, dict):
            raise GeminiError("Resposta do Gemini fora do formato esperado")
        return result
