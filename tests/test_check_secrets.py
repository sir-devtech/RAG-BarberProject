from scripts.check_secrets import scan_text


def kinds(text: str) -> set[str]:
    return {f.kind for f in scan_text(text)}


# Valores falsos montados em pedacos: o proprio arquivo de teste nao pode parecer segredo.
FAKE_KEY = "AI" + "za" + "A" * 35
FAKE_CPF = "123.456." + "789-09"
FAKE_PHONE = "(11) 9" + "8765-4321"
FAKE_IP = ".".join(["203", "0", "113", "7"])


def test_detecta_chave_gemini() -> None:
    assert "chave Google/Gemini" in kinds(f"GEMINI_API_KEY={FAKE_KEY}")


def test_detecta_dados_pessoais() -> None:
    assert "CPF" in kinds(f"cliente {FAKE_CPF}")
    assert "telefone BR" in kinds(f"ligar {FAKE_PHONE}")


def test_detecta_infraestrutura() -> None:
    assert "endereco IP" in kinds(f"host {FAKE_IP}")
    assert "caminho de servidor" in kinds("cd /opt" + "/app")
    assert "chave SSH" in kinds("ssh -i ~/.ssh/id_" + "ed25519")


def test_aceita_local_e_texto_normal() -> None:
    assert kinds("servidor em 127.0.0.1 na porta 8000") == set()
    assert kinds("O plano de 3 barbeiros custa R$ 160 por mes.") == set()
    assert kinds("GEMINI_API_KEY=cole-sua-chave-aqui") == set()


def test_achado_nunca_traz_o_valor() -> None:
    finding = scan_text(f"x {FAKE_KEY}")[0]
    assert FAKE_KEY not in repr(finding)
