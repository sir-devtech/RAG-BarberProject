from app.retrieval.text import strip_accents, tokenize


def test_tira_acento_e_poe_em_minusculas() -> None:
    assert strip_accents("Preços Média") == "Precos Media"
    assert tokenize("Preços") == tokenize("precos") == ["preco"]


def test_plural_simples_vira_singular() -> None:
    assert tokenize("barbeiros") == tokenize("barbeiro") == ["barbeiro"]


def test_numeros_ficam_inteiros_e_simbolo_de_moeda_some() -> None:
    assert tokenize("R$ 250") == ["250"]
    assert tokenize("R$ 1250,90") == ["1250", "90"]


def test_palavras_comuns_sao_descartadas() -> None:
    assert tokenize("o plano de um barbeiro") == ["plano", "barbeiro"]


def test_palavras_curtas_nao_perdem_o_s() -> None:
    assert tokenize("mes") == ["mes"]
