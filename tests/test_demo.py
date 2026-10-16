from scripts.demo import DEMO, DEMO_IDS, load_demo_results, render


def test_a_demonstracao_cobre_os_casos_que_prometeu() -> None:
    results = load_demo_results()
    assert list(results) == DEMO_IDS  # todo caso existe, na ordem, e o cassete tem a gravacao


def test_cenas_mostram_o_comportamento_descrito() -> None:
    results = load_demo_results()
    assert results["t02"].answer.grounded and "250" in results["t02"].answer.text
    assert results["t10"].answer.grounded and "250" in results["t10"].answer.text  # corrige R$ 200
    assert not results["t12"].answer.grounded  # fora do assunto
    assert not results["t15"].answer.grounded  # manipulacao
    assert not results["v20"].answer.grounded  # a falha conhecida continua visivel, nao escondida


def test_render_mostra_pergunta_resposta_fonte_e_motivo() -> None:
    results = load_demo_results()
    texto = render("t02", DEMO[0][1], results["t02"], 1, len(DEMO))
    for parte in ["PERGUNTA", "RESPONDEU", "FONTE", "MOTIVO", "ferramenta"]:
        assert parte in texto


def test_nada_na_saida_parece_segredo() -> None:
    from scripts.check_secrets import scan_text

    results = load_demo_results()
    saida = "\n".join(
        render(i, n, results[i], k, len(DEMO)) for k, (i, n) in enumerate(DEMO, start=1)
    )
    assert scan_text(saida) == []
