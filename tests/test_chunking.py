import pytest

from app.ingest.chunking import Chunk, chunk_markdown

DOC = """# Planos

Texto de abertura dos planos.

## Simples Solo

O plano Simples Solo custa R$ 120 por mes.

## Simples Pequena

O plano Simples Pequena custa R$ 160 por mes.
"""


def chunk(text: str, **kwargs: int) -> list[Chunk]:
    return chunk_markdown(text, tenant="loja-a", source="loja-a/x.md", **kwargs)


def paragrafos(quantidade: int) -> str:
    """Paragrafos de 44 caracteres, separados por linha em branco."""
    itens = (f"Paragrafo numero {i:02d} com texto de enchimento." for i in range(quantidade))
    return "\n\n".join(itens)


def test_divide_por_titulos_e_guarda_a_trilha() -> None:
    chunks = chunk(DOC)
    assert [c.heading for c in chunks] == [
        "Planos",
        "Planos > Simples Solo",
        "Planos > Simples Pequena",
    ]


def test_trilha_vai_junto_no_texto_do_embedding() -> None:
    pequena = chunk(DOC)[2]
    assert pequena.text.startswith("Planos > Simples Pequena\n")
    assert "R$ 160" in pequena.text


def test_secao_sem_corpo_e_descartada() -> None:
    assert chunk("# So titulo\n\n## Outro titulo\n") == []


def test_secao_grande_e_dividida_sem_passar_do_limite() -> None:
    chunks = chunk(f"# Longo\n\n{paragrafos(30)}", max_chars=200)
    assert len(chunks) > 1
    assert all(len(c.body) <= 200 for c in chunks)


def test_overlap_repete_a_ultima_unidade_do_chunk_anterior() -> None:
    doc = f"# T\n\n{paragrafos(12)}"
    com = chunk(doc, max_chars=120, overlap_units=1)
    sem = chunk(doc, max_chars=120, overlap_units=0)
    ultima_do_primeiro = com[0].body.splitlines()[-1]
    assert ultima_do_primeiro in com[1].body
    assert ultima_do_primeiro not in sem[1].body
    assert all(len(c.body) <= 120 for c in com)


def test_lista_longa_sem_pontuacao_e_dividida_por_linha() -> None:
    itens = "\n".join(f"- item numero {i:02d} da lista de recursos" for i in range(20))
    chunks = chunk(f"# Recursos\n\n{itens}", max_chars=150)
    assert len(chunks) > 1
    assert all(len(c.body) <= 150 for c in chunks)


def test_ids_sao_estaveis_e_unicos_e_hash_acompanha_o_texto() -> None:
    a, b = chunk(DOC), chunk(DOC)
    assert [c.id for c in a] == [c.id for c in b]
    assert len({c.id for c in a}) == len(a)
    mudou = chunk(DOC.replace("R$ 160", "R$ 170"))
    assert a[2].content_hash != mudou[2].content_hash
    assert a[1].content_hash == mudou[1].content_hash


def test_guarda_loja_e_origem() -> None:
    c = chunk(DOC)[0]
    assert (c.tenant, c.source) == ("loja-a", "loja-a/x.md")


def test_limite_muito_pequeno_e_recusado() -> None:
    with pytest.raises(ValueError):
        chunk(DOC, max_chars=10)
