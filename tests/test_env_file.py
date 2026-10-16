from pathlib import Path

import pytest

from app.config import Settings, read_env_file


def test_le_arquivo_env_ignorando_comentarios_e_aspas(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('# comentario\n\nA=1\nB="dois"\nC=\n', encoding="utf-8")
    assert read_env_file(env) == {"A": "1", "B": "dois", "C": ""}


def test_arquivo_inexistente_vira_dicionario_vazio(tmp_path: Path) -> None:
    assert read_env_file(tmp_path / "nao-existe") == {}


def test_load_usa_o_arquivo_e_o_ambiente_tem_prioridade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env"
    # Valores falsos montados em partes: o teste nao pode parecer um segredo de verdade.
    pares = {"GEMINI_API_KEY": "fake", "GEMINI_CHAT_MODEL": "chat", "GEMINI_EMBEDDING_MODEL": "emb"}
    env.write_text("".join(f"{nome}={valor}\n" for nome, valor in pares.items()), encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert Settings.load(env).chat_model == "chat"
    monkeypatch.setenv("GEMINI_CHAT_MODEL", "do-ambiente")
    assert Settings.load(env).chat_model == "do-ambiente"
