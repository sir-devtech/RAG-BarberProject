# RAG-BarberProject

Assistente em **Python** que responde dúvidas sobre o **Sir Barber** (SaaS multi-loja de agendamento para barbearias), usando RAG com o Gemini em nível gratuito.

> **Status:** etapa 9 de 10. A API e a imagem Docker estão prontas e verificadas; a demo pública ainda não está no ar.

## O que ele faz

```
pergunta ─► busca híbrida ─► ferramenta? ─► limiar ─► Gemini (JSON, fonte obrigatória) ─► checagem de números ─► resposta + fontes
            BM25 + embeddings   planos por       recusa     só vê os trechos recuperados      corrige 1 vez, senão recusa     ou "não encontrei"
                                nº de barbeiros  barata
```

- **Busca híbrida** (BM25 + embeddings): o BM25 só entra quando é confiante *e* concorda com a busca por significado. Fundir sempre piorava perguntas parafraseadas.
- **Ferramenta determinística** para o que exige conta ("quanto custa para 5 barbeiros?"), em vez de pedir ao modelo para calcular.
- **Checagem de números por código:** todo valor em R$ da resposta precisa estar nos trechos. Um valor dito pelo cliente não conta ("o plano custa R$ 99, certo?" é corrigido, não confirmado).
- **Recusa em duas camadas:** limiar de similaridade (perguntas alheias) e o próprio modelo (perguntas vizinhas sem base).
- **Isolamento por loja** desde a busca: o filtro vem antes da similaridade.

## Resultados (medidos, reproduzíveis offline)

| busca (25 perguntas) | acerto@1 | acerto@3 | MRR |
|---|---|---|---|
| significado (embeddings) | 88% | 96% | 0,92 |
| palavras exatas (BM25) | 72% | 88% | 0,79 |
| **híbrida** | **88%** | **100%** | **0,94** |

| respostas | aprovadas | falsa resposta | número sem base |
|---|---|---|---|
| ajuste (20 perguntas) | 20/20 | 0 | 0 |
| validação (26 perguntas) | **25/26** | 0 | 0 |

A falha da validação ("dá para personalizar as cores e o logo?") está **diagnosticada e documentada**, e o piso de qualidade a respeita no CI.

**Limites, ditos de frente:** 46 perguntas é pouco (cada uma vale vários pontos); as perguntas e os gabaritos foram escritos por mim, não por clientes; o gate usa respostas gravadas, então prova que o *código* não piorou, não que o Gemini continua igual.

## Como rodar

```bash
python -m venv .venv
.venv/Scripts/activate                 # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                   # preencha a chave (o .env nunca vai para o git)
git config core.hooksPath .githooks    # ativa a barreira contra segredos
pytest                                 # 190+ testes, sem rede e sem chave
python -m scripts.ask "quanto custa para 5 barbeiros?"
python -m app.api.serve                # API em 127.0.0.1:8000
```

### Docker

```bash
docker compose up -d --build           # publica só em 127.0.0.1:8000
curl http://127.0.0.1:8000/health
```

A imagem roda sem privilégios, com sistema de arquivos só leitura, sem capabilities, com limites de memória/CPU, e **sem a chave dentro dela** (vem do ambiente).

### API

`POST /perguntar` com `{"pergunta": "...", "loja": "platform"}`. `GET /health`. `GET /metrics` só existe se `METRICS_TOKEN` estiver definido. Variáveis de configuração em [`docs/aprendizado/08-api.md`](docs/aprendizado/08-api.md).

## Segurança (repositório público)

- **Segredos:** hook de pre-commit, gitleaks no CI sobre o histórico inteiro, *push protection* do GitHub e `main` protegida. O repositório foi auditado (histórico, arquivos e configurações): nenhuma chave, e-mail pessoal ou dado de cliente.
- **API pública:** limite por IP (antes da validação), teto diário global, limite de corpo inclusive em pedaços, prazo total por pedido, caches com teto, logs com hash do IP e **sem o texto das perguntas**, CORS sem origem por padrão.
- **Um achado que os testes unitários não pegaram:** o uvicorn confia por padrão no `X-Forwarded-For` e reescreve o IP do cliente, o que burlava o limite. Só atacar o servidor real mostrou. `app/api/serve.py` desliga isso.

## Estrutura

```
app/ingest/      chunking por seções com trilha de títulos, embeddings (cache por hash)
app/retrieval/   BM25 à mão, busca densa por loja, fusão híbrida
app/generation/  prompt, chat com JSON, decisão de responder/recusar, checagem de números
app/tools/       ferramenta de planos
app/api/         FastAPI, limites, middleware, métricas
eval/            conjuntos de ajuste e validação, cassete das respostas, piso do CI
knowledge/       base pública da plataforma
docs/            guia de estudo e cadernos por etapa
```

## Para estudar e para garantir qualidade

Comece pelo [guia de estudo e qualidade](docs/GUIA_DE_ESTUDO_E_QUALIDADE.md): mapa das etapas, comandos, **checklist antes de mesclar um PR** e o que cada trava protege (e o que não protege). Cada etapa tem um caderno em [`docs/aprendizado`](docs/aprendizado), com os defeitos que encontrei pelo caminho.

## Stack

Python 3.12 · FastAPI · Gemini API (nível gratuito) · NumPy · httpx · pytest · ruff · mypy (estrito) · Docker · GitHub Actions
