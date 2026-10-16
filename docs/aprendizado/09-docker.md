# Etapa 9 — Empacotar em Docker

## O que foi feito
- `Dockerfile`, `.dockerignore`, `docker-compose.yml`.
- `tests/test_container.py`: 8 garantias sobre a imagem que rodam **sem Docker**, no CI.
- README final.

> **Status:** imagem **construída e atacada** em 16/10/2026 (Docker Desktop, engine 29.x). Resultados na seção "Verificação real".

## Conceito: a imagem é uma foto do que foi copiado
Tudo que entra na imagem pode acabar num registry ou em outra máquina. Por isso a regra é **copiar o mínimo**: o código da API e a base de conhecimento. Testes, avaliação, scripts, docs, o `.env`, o `.git` e o `.index` ficam de fora.

## Decisões
| decisão | por quê |
|---|---|
| a chave **não entra** na imagem; vem do ambiente (`env_file`) | uma imagem com a chave dentro vaza para quem a puxar |
| usuário `app` (uid 10001), sem shell de login | se o processo for invadido, não tem privilégio de root |
| lista de dependências lida do `pyproject.toml` | fonte única; evita um `requirements.txt` que diverge |
| dependências antes do código no Dockerfile | só refaz a camada pesada quando as dependências mudam |
| `read_only`, `cap_drop: ALL`, `no-new-privileges` | reduz o que um invasor consegue fazer |
| `mem_limit`, `cpus`, `pids_limit` | um pedido malicioso não derruba o servidor inteiro (o droplet divide recursos com o Multi) |
| porta publicada só em `127.0.0.1` | expor para a internet é decisão consciente, via proxy reverso |
| `HEALTHCHECK` | o Docker reinicia o container se `/health` parar de responder |
| comando `python -m app.api.serve` | sobe com `proxy_headers=False` (ver caderno 08) |

## Um erro meu, pego antes do build
Escrevi no `.dockerignore` a linha `*.md` para não levar o README. Mas a base de conhecimento são arquivos `.md` em `knowledge/platform/`: dependendo de como o padrão fosse interpretado, a imagem subiria **sem dados**. Troquei por `README.md` e criei um teste que confere que a base e o código **não** são ignorados e que `.env`, `.git` e `.index` **são**. Lição: o `.dockerignore` é código; teste.

## Riscos que ficam para a etapa 10
- **O IP do cliente.** Atrás de um proxy reverso no mesmo servidor, o IP que a API enxerga é o do proxy, e **todos os visitantes viram o mesmo cliente** para o limite. Será preciso configurar `CLIENT_IP_HEADER` com o cabeçalho que o proxy sobrescreve, e garantir que o container só receba tráfego do proxy.
- **Primeira subida:** gera os vetores da base (22 chamadas ao Gemini em um lote) e grava em `/data`. Se a chave estiver errada, o container cai na subida: é intencional (falhar cedo).
- **O volume `/data`** guarda só vetores de texto público; não tem dado de usuário.

## Verificação real (todos os itens da lista original, medidos)
- [x] `docker compose build` terminou sem erro: imagem de **297 MB**.
- [x] O processo roda como `uid=10001(app)`, shell `nologin`. Não é root.
- [x] `/app` contém só `app`, `knowledge` e `pyproject.toml`. **Sem** `.env`, `.git`, `tests`, `eval`, `docs`, `scripts`. O `pyproject.toml` fica porque foi usado para instalar as dependências; não tem segredo.
- [x] Nenhum arquivo da imagem com formato de chave; nenhuma variável de ambiente de segredo. O único `GPG_KEY` é a chave **pública** de assinatura do Python, da imagem base.
- [x] Sobe `healthy` em ~8 s. A primeira subida gera os 22 vetores (1 chamada ao Gemini).
- [x] `read_only`: gravar em `/` e `/app` falha ("Read-only file system"); `/data` e `/tmp` funcionam.
- [x] **Zero capabilities** (`CapEff` e `CapPrm` = 0), `no-new-privileges` ativo.
- [x] Limites aplicados: 384 MB, 0,5 CPU, 128 processos. Uso real: **47 MiB**, 17 processos.
- [x] Os mesmos ataques da etapa 8, contra o container: pergunta real ok; loja inválida 404; `../../etc` 422; corpo de 100 KB 413; `/metrics` e `/docs` 404; IPs falsos no `X-Forwarded-For` **não burlam** o limite (6 válidos, o 7º leva 429); cabeçalhos de segurança presentes; log sem texto de pergunta.
- [x] O container não alcança a porta 5432 do host (os bancos do Multi ficam isolados).

**Observação sobre o IP:** neste teste todos os pedidos chegam ao container com o mesmo IP (o do gateway do Docker), então o limite vale para o conjunto. É exatamente o risco descrito acima, e é por isso que a etapa 10 precisa de `CLIENT_IP_HEADER`.

## Como explicar na entrevista (2 frases)
"Empacotei a API sem a chave dentro da imagem, com usuário sem privilégios, sistema de arquivos só leitura, sem capabilities e com limites de recurso, publicando só em localhost. E escrevi testes que verificam a imagem sem precisar do Docker, porque descobri que um padrão errado no `.dockerignore` poderia deixar a base de conhecimento de fora."

## Perguntas para você responder com as suas palavras
1. Por que a chave vem do ambiente e não é copiada para a imagem?
2. O que acontece com o limite por IP quando a API fica atrás de um proxy no mesmo servidor?
3. Por que o `.dockerignore` merece teste?
