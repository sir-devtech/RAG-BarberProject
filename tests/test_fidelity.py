from decimal import Decimal

from app.generation.fidelity import numbers_in, ungrounded_numbers


def test_reconhece_formatos_brasileiros() -> None:
    assert set(numbers_in("R$ 1.250,90 e R$ 250 e 15 dias")) == {
        Decimal("1250.90"), Decimal("250"), Decimal("15"),
    }  # fmt: skip


def test_250_e_250_virgula_00_sao_o_mesmo_valor() -> None:
    assert ungrounded_numbers("R$ 250,00", ["custa R$ 250"]) == []


def test_numero_que_nao_esta_no_contexto_e_apontado() -> None:
    assert ungrounded_numbers("Custa R$ 199 por 30 dias", ["custa R$ 160 por 30 dias"]) == ["199"]


def test_aceita_numero_vindo_de_qualquer_texto_permitido() -> None:
    assert ungrounded_numbers("3 barbeiros por R$ 160", ["pergunta: 3 barbeiros", "R$ 160"]) == []


def test_resposta_sem_numeros_e_sempre_fiel() -> None:
    assert ungrounded_numbers("Pode cancelar quando quiser.", ["texto sem numeros"]) == []


def test_ponto_so_e_milhar_com_tres_digitos() -> None:
    assert Decimal("1250") in numbers_in("R$ 1.250")
    assert Decimal("1.5") not in numbers_in("R$ 1.250")


def test_valor_em_reais_nunca_vem_so_da_pergunta() -> None:
    contexto = ["O plano Solo custa R$ 120 por mês."]
    pergunta = ["o plano Solo custa R$ 99, certo?"]
    assert ungrounded_numbers("Sim, custa R$ 99.", contexto, pergunta) == ["99"]
    assert ungrounded_numbers("Não, custa R$ 120.", contexto, pergunta) == []


def test_quantidade_da_pergunta_pode_ser_repetida() -> None:
    contexto = ["Simples Média: R$ 250 por mês, de 4 a 8 barbeiros."]
    assert ungrounded_numbers("Para 5 barbeiros: R$ 250.", contexto, ["para 5 barbeiros?"]) == []


def test_numero_so_na_pergunta_e_fora_de_dinheiro_e_aceito_mas_nao_o_inventado() -> None:
    contexto = ["De 4 a 8 barbeiros."]
    assert ungrounded_numbers("Para 5 barbeiros, 30 dias.", contexto, ["5 barbeiros?"]) == ["30"]
