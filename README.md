# RAG-BarberProject

Assistente em Python que responde dúvidas de clientes de barbearias do **Sir Barber**
(SaaS multi-loja de agendamento), usando RAG com Gemini em nível gratuito.

> **Status:** em construção, etapa 8 de 10 (API com defesas de abuso).

## O que o projeto vai ter

- Busca **híbrida** (BM25 + embeddings) com filtro por loja.
- Roteamento entre **documentos** (políticas) e **ferramentas** (preço e agenda ao vivo).
- Checagem de **fidelidade numérica**: a resposta não pode citar valor que não veio da fonte.
- **Avaliação automatizada** como gate de CI.

## Rodar localmente

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
git config core.hooksPath .githooks   # ativa a barreira contra segredos
cp .env.example .env                  # e preencha (o .env nunca vai para o git)
pytest
```

## Segurança (repositório público)

Nenhuma chave, dado de cliente ou endereço de servidor entra aqui. Três barreiras:
hook de pre-commit (`scripts/check_secrets.py`), CI com gitleaks no histórico inteiro
e o *push protection* do GitHub.

Para **estudar** e para **conferir a qualidade** antes de mudar algo, comece pelo
[`guia de estudo e qualidade`](docs/GUIA_DE_ESTUDO_E_QUALIDADE.md). O passo a passo detalhado de
cada etapa está em [`docs/aprendizado`](docs/aprendizado).
