# Etapa 8 — A API (e como ela se defende)

## O que foi feito
- `app/api/main.py`: FastAPI com `POST /perguntar`, `GET /health` e `GET /metrics` (opcional).
- `app/api/serve.py`: ponto de entrada do servidor (`python -m app.api.serve`).
- `app/api/limits.py`: limite por IP (janela deslizante) e teto diário global.
- `app/api/middleware.py`: limite de corpo e cabeçalhos de segurança.
- `app/api/lru.py`, `metrics.py`, `settings.py`, `service.py`.
- Prazo total por pedido em `app/gemini.py`.
- 48 testes novos (185 no total), sem rede.

## Conceito: uma API pública é uma superfície de ataque
Até aqui o assistente só falava com você. Agora qualquer pessoa pode mandar texto. O que importa deixa de ser "funciona?" e passa a ser "o que acontece quando alguém abusa?". Cada defesa responde a um abuso concreto:

| abuso | defesa |
|---|---|
| esgotar a cota gratuita do Gemini | limite por IP (6/min, 60/dia) **e** teto diário global (400) |
| corpo gigante, inclusive enviado em pedaços | limite de bytes cortado **durante** o recebimento (413) |
| gastar threads com chamadas lentas | **prazo total** de 25 s por pedido, somando as retentativas |
| encher a memória com perguntas únicas | cache de vetores com teto (LRU de 256); tabela de IPs com teto (10 mil) |
| descobrir como o servidor falha | erro do Gemini vira "indisponível" genérico; erro interno vira `{"erro": "Erro interno."}` sem stack |
| espionar quem pergunta | log com **hash do IP** (com sal) e só o **tamanho** da pergunta, nunca o texto |
| enumerar lojas | loja fora da lista dá 404, igual a "inexistente"; nome de loja só aceita `[a-z0-9-]` |
| ver métricas | `/metrics` **nem existe** sem token; com token, comparação em tempo constante |
| usar o navegador de outro site | CORS sem nenhuma origem por padrão; `*` é recusado |
| fingir ser outro IP | só se confia em um cabeçalho que **você** configurar (`CLIENT_IP_HEADER`) |

A **ordem** importa: o limite por IP roda **antes** da validação, para que quem manda lixo em massa também gaste o limite (um teste cobre isso).

## Três defeitos que só apareceram testando de verdade
1. **O limitador quebrava sob ataque de IPs inventados.** Quando a tabela enchia, a limpeza apagava justamente a entrada recém-criada (vazia), e a linha seguinte dava `KeyError`. Um atacante com IPs falsos derrubaria os pedidos. O teste de "memória nunca passa do teto" achou.
2. **Corpo em pedaços virava 400, não 413.** O FastAPI captura qualquer erro ao ler o corpo e o converte em 400, então a minha exceção nunca era vista. A saída foi sinalizar o excesso, descartar a resposta do app e responder 413 eu mesmo.
3. **O uvicorn burlava o meu limite por IP** (o mais importante). Por padrão ele confia em `X-Forwarded-For` de quem vem de `127.0.0.1` e **reescreve o IP do cliente** antes de a aplicação ver. Meus testes passaram porque o `TestClient` não usa o uvicorn. Só o ataque contra o servidor real mostrou: com limite 4/min, três pedidos com IPs falsos passaram. Também o log de acesso do uvicorn imprimia o IP de todo visitante. Correção: `serve.py` sobe o uvicorn com `proxy_headers=False`, `access_log=False` e `server_header=False`. **Repetido o ataque:** 4 passam, o 5º e o 6º recebem 429 com `Retry-After`.

Lição: um teste que **não passa pelo servidor de verdade** não prova uma defesa de rede.

Um quarto achado veio da latência: respostas de 7 s a 23 s (retentativas por erro 503 do Gemini). Com o cliente antigo, um pedido podia prender uma thread por minutos (timeout de 60 s × 4 tentativas). Agora cada pedido tem prazo total de 25 s.

## Como o IP é decidido
- Padrão: o IP do socket (quem conectou).
- Atrás de um proxy confiável (nginx/Cloudflare): defina `CLIENT_IP_HEADER` com o cabeçalho **que esse proxy sobrescreve** (ex.: `CF-Connecting-IP`).
- **Risco:** se a API ficar acessível sem passar pelo proxy, qualquer um forjaria o cabeçalho. Por isso o container só deve receber tráfego do proxy (etapa 9/10).

## Configuração (variáveis de ambiente)
| variável | padrão | efeito |
|---|---|---|
| `ALLOWED_TENANTS` | `platform` | lojas atendidas (valida o nome) |
| `RATE_PER_MINUTE` / `RATE_PER_DAY` | 6 / 60 | limite por IP |
| `DAILY_CAP` | 400 | teto diário global |
| `MAX_BODY_BYTES` | 4096 | tamanho máximo do corpo |
| `CLIENT_IP_HEADER` | vazio | cabeçalho do IP real (só atrás de proxy confiável) |
| `CORS_ORIGINS` | vazio | origens `https://…` permitidas (`*` é recusado) |
| `METRICS_TOKEN` | vazio | liga `/metrics` (mínimo de 16 caracteres) |
| `ENABLE_DOCS` | desligado | liga `/docs` |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | onde escuta (expor é decisão consciente) |

Valor inválido derruba a subida: falhar cedo é melhor que rodar com a defesa desligada sem perceber.

## Ressalvas honestas
- **Limites em memória:** reiniciar o serviço zera os contadores, e mais de uma instância não os compartilha. Para uma demo, ok.
- **Latência:** 4 a 8 s por pergunta é típico; ocasionalmente 20 s+ quando o Gemini está sobrecarregado.
- **Não testei carga real** (centenas de pedidos simultâneos); testei abusos individuais.
- A defesa contra IP falso **depende da implantação** (o container só pode receber tráfego do proxy).
- Sem autenticação: qualquer um pode perguntar. É intencional (demo pública), e por isso existem os tetos.

## Alternativas descartadas
- **`slowapi`:** funciona, mas esconde a lógica e não cobre o teto diário nem a tabela com limite de memória.
- **Redis para os limites:** exagero para uma instância só.
- **Autenticação por chave:** impede a demo pública.

## Como explicar na entrevista (2 frases)
"Tratei a API como superfície de ataque: limite por IP antes da validação, teto diário para proteger a cota gratuita, prazo total por pedido, memória com teto e logs sem texto de pergunta nem IP. E testei contra o servidor de verdade, o que mostrou que o uvicorn reescrevia o IP a partir do `X-Forwarded-For` e burlava o limite, algo que o `TestClient` nunca revelaria."

## Perguntas para você responder com as suas palavras
1. Por que o limite por IP vem **antes** da validação do corpo?
2. Por que o `TestClient` não encontrou o problema do `X-Forwarded-For`, e o que encontrou?
3. Por que o prazo total por pedido protege a API mesmo sem nenhum atacante grande?
