from pathlib import Path

import pytest

from app.ingest.loader import load_tenant_chunks


def test_recusa_nome_de_loja_com_caminho(tmp_path: Path) -> None:
    for tenant in ["../segredo", "a/b", "A", "", "loja a"]:
        with pytest.raises(ValueError):
            load_tenant_chunks(tenant, knowledge_dir=tmp_path)


def test_loja_sem_base_da_erro_claro(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_tenant_chunks("nao-existe", knowledge_dir=tmp_path)


def test_isolamento_cada_loja_so_ve_a_propria_base(tmp_path: Path) -> None:
    for tenant, price in [("loja-a", "R$ 40"), ("loja-b", "R$ 90")]:
        (tmp_path / tenant).mkdir()
        (tmp_path / tenant / "servicos.md").write_text(
            f"# Servicos\n\n## Corte\n\nO corte custa {price}.\n", encoding="utf-8"
        )
    a = load_tenant_chunks("loja-a", knowledge_dir=tmp_path)
    assert a and all(c.tenant == "loja-a" for c in a)
    assert all("R$ 90" not in c.text for c in a)


def test_base_real_da_plataforma_cada_preco_fica_com_o_nome_do_plano() -> None:
    chunks = load_tenant_chunks("platform")
    esperado = {
        "Simples Solo": "R$ 120",
        "Simples Pequena": "R$ 160",
        "Simples Média": "R$ 250",
        "Simples Grande": "R$ 350",
        "Plano Completo": "R$ 329",
        "Plano Premium": "R$ 650",
    }
    for plano, preco in esperado.items():
        achados = [c for c in chunks if c.heading.endswith(plano)]
        assert achados, f"sem chunk para {plano}"
        assert any(preco in c.text for c in achados), f"{plano} sem {preco}"


def test_base_real_nenhum_chunk_passa_do_limite() -> None:
    assert all(len(c.body) <= 600 for c in load_tenant_chunks("platform"))
