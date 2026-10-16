import pytest

from app.config import MissingSettingError, Settings

VALID = {
    "GEMINI_API_KEY": "chave-de-teste",
    "GEMINI_CHAT_MODEL": "modelo-chat",
    "GEMINI_EMBEDDING_MODEL": "modelo-embedding",
}


def test_le_configuracao_do_ambiente() -> None:
    settings = Settings.from_env(VALID)
    assert settings.chat_model == "modelo-chat"
    assert settings.embedding_model == "modelo-embedding"


def test_erro_lista_so_nomes_faltando() -> None:
    with pytest.raises(MissingSettingError) as err:
        Settings.from_env({"GEMINI_API_KEY": "chave-de-teste"})
    assert "GEMINI_CHAT_MODEL" in str(err.value)
    assert "chave-de-teste" not in str(err.value)


def test_repr_nao_vaza_a_chave() -> None:
    assert "chave-de-teste" not in repr(Settings.from_env(VALID))
