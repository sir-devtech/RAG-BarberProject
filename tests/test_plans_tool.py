import json
import re

import pytest

from app.ingest.loader import load_tenant_chunks
from app.tools.plans import (
    PLANS_FILE,
    PlansTool,
    describe,
    extract_barber_count,
    load_plans,
    plans_for,
)

PLANS = load_plans()


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("quanto custa para 5 barbeiros?", 5),
        ("tenho 12 profissionais", 12),
        ("somos três barbeiros", 3),
        ("uma equipe de dois funcionários", 2),
        ("quanto custa o Premium?", None),
        ("o plano de R$ 250", None),
        ("0 barbeiros", None),
    ],
)
def test_extrai_a_quantidade_de_barbeiros(question: str, expected: int | None) -> None:
    assert extract_barber_count(question) == expected


@pytest.mark.parametrize(
    ("barbers", "names"),
    [
        (1, {"Simples Solo", "Completo"}),
        (3, {"Simples Pequena", "Completo"}),
        (5, {"Simples Média", "Completo"}),
        (8, {"Simples Média", "Completo", "Premium"}),
        (10, {"Simples Grande", "Premium"}),
        (12, {"Simples Grande", "Premium"}),
        (13, set()),
    ],
)
def test_planos_por_numero_de_barbeiros(barbers: int, names: set[str]) -> None:
    assert {p.name for p in plans_for(barbers, PLANS)} == names


def test_descricao_traz_valores_faixas_e_se_tem_asaas() -> None:
    text = describe(5, PLANS)
    assert "Simples Média: R$ 250 por mês, para 4 a 8 barbeiros, sem cobrança Asaas" in text
    assert "Completo: a partir de R$ 329 por mês, para 1 a 8 barbeiros, com cobrança Asaas" in text


def test_acima_do_maximo_diz_que_nao_ha_plano() -> None:
    assert "vão até 12 barbeiros" in describe(20, PLANS)


def test_ferramenta_so_age_na_base_da_plataforma() -> None:
    tool = PlansTool(PLANS)
    assert tool.hits("quanto custa para 5 barbeiros?", "outra-loja") == []
    assert tool.hits("quanto custa o Premium?", "platform") == []
    hit = tool.hits("quanto custa para 5 barbeiros?", "platform")[0]
    assert hit.chunk.source == "ferramenta:planos" and hit.chunk.tenant == "platform"


def test_json_e_texto_da_base_nunca_divergem() -> None:
    """Se alguem mudar um preco so no JSON (ou so no markdown), este teste avisa."""
    secoes = {c.heading.split(" > ")[-1]: c.text for c in load_tenant_chunks("platform")}
    for raw in json.loads(PLANS_FILE.read_text(encoding="utf-8")):
        nome = raw["name"] if raw["name"].startswith("Simples") else f"Plano {raw['name']}"
        assert nome in secoes, f"sem secao para {nome}"
        precos = re.findall(r"R\$ (\d+)", secoes[nome])
        assert str(raw["price"]) in precos, f"{nome}: JSON diz {raw['price']}, texto diz {precos}"
