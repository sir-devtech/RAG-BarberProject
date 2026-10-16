# Guia de estudo e garantia de qualidade

Documento único para **estudar** o projeto e para **conferir a qualidade** antes de qualquer mudança. Cada etapa tem um caderno detalhado em [`docs/aprendizado/`](aprendizado); aqui está o mapa.

> **Como usar:** para estudar, leia na ordem 1 a 7 e responda as perguntas do fim de cada caderno com as suas palavras. Para garantir qualidade, use o checklist da seção 3.

## 1. O mapa em uma tela

```
pergunta ──► [busca] ──► [ferramenta?] ──► [limiar] ──► [Gemini + regras] ──► [checagem de números] ──► resposta + fontes
              BM25 +        planos por        recusa        saída JSON,           corrige 1 vez,             ou "não encontrei"
              embeddings    nº de barbeiros   barata        fonte obrigatória     senão recusa
```

| # | Etapa | Ideia central | Caderno |
|---|---|---|---|
| 1 | Estrutura e segurança | Repo **público**: ninguém pode vazar chave nem dado. Três barreiras (hook, CI/gitleaks, push protection). | [01](aprendizado/01-estrutura-e-seguranca.md) |
| 2 | Chunking | Cortar a base por seções e levar a **trilha de títulos** em cada pedaço, para o preço nunca ficar sem o nome do plano. | [02](aprendizado/02-chunking.md) |
| 3 | Embeddings | Texto vira coordenadas de **significado**; cosseno mede proximidade; filtro por loja **antes** de comparar. | [03](aprendizado/03-embeddings-e-busca-densa.md) |
| 4 | Busca híbrida | BM25 acerta palavra exata; embeddings acertam sinônimo; fundir **sempre** piora paráfrases, então o BM25 só entra se **confiante e concordante**. | [04](aprendizado/04-busca-hibrida-e-avaliacao.md) |
| 5 | Geração e recusa | O modelo só vê trechos; recusa em **duas camadas** (limiar + modelo); fonte obrigatória; trechos escapados contra injeção. | [05](aprendizado/05-geracao-e-recusa.md) |
| 6 | Fidelidade e ferramenta | Números da resposta checados **por código**; conta ("5 barbeiros") feita por ferramenta, não pelo modelo. | [06](aprendizado/06-fidelidade-e-ferramenta.md) |
| 7 | Avaliação de respostas | Conjuntos de **ajuste e validação**, cassete e **gate no CI**. | [07](aprendizado/07-avaliacao-de-respostas.md) |
| 8 | API | Limite por IP **antes** da validação, teto diário, prazo por pedido, logs sem texto nem IP; o uvicorn burlava o limite por padrão. | [08](aprendizado/08-api.md) |
| 9 | Docker | Imagem sem chave, sem root, só leitura, limites de recurso; testes da imagem que rodam sem Docker. | [09](aprendizado/09-docker.md) |
| 10 | Fechamento | **Sem demo hospedada**: o servidor tinha pouca memória livre e a hospedagem gratuita exigia plano pago. Demonstração offline + roteiro de vídeo. | [10](aprendizado/10-decisao-sem-demo-publica.md) |

## 2. Comandos (rode você mesmo)

```bash
cd C:\RAG-BarberProject
.venv\Scripts\pytest -q                                # todos os testes (offline, sem chave)
.venv\Scripts\ruff check .                             # estilo e erros comuns
.venv\Scripts\mypy                                     # tipos (modo estrito)
python scripts\check_secrets.py                        # segredos e dados pessoais nos arquivos versionados

.venv\Scripts\python -m scripts.show_chunks platform   # ver como a base foi dividida
.venv\Scripts\python -m scripts.ask_dense "pergunta"   # só busca por significado (usa a chave)
.venv\Scripts\python -m scripts.ask --debug "pergunta" # pipeline completo, mostra os trechos entregues
.venv\Scripts\python -m eval.run_eval --sweep          # avaliação da BUSCA (25 perguntas)
.venv\Scripts\python -m eval.run_answers --verbose     # avaliação das RESPOSTAS (offline, do cassete)
.venv\Scripts\python -m scripts.demo                 # demonstração offline em 9 cenas (sem chave)
.venv\Scripts\python -m eval.run_answers --record      # regrava o cassete (usa a chave e a cota)
```

## 2b. Docker: usar e limpar sem deixar rastro

```bash
docker compose up -d --build        # sobe (publica so em 127.0.0.1:8000; nao reinicia sozinho)
docker compose down -v              # desliga e apaga container, rede e volume do projeto
docker image rm rag-barberproject:local   # apaga a imagem (se refaz em segundos)
```

O compose nunca monta pastas do seu computador. Esses comandos so mexem em coisas com o nome deste projeto.

## 3. Checklist de qualidade (antes de mesclar qualquer PR)

- [ ] `pytest`, `ruff` e `mypy` verdes (o CI repete isso).
- [ ] `check_secrets.py` sem achados e **nenhum** `.env` no commit (o hook barra, confira mesmo assim).
- [ ] Mudou a **base de conhecimento**, o **prompt**, as **regras de busca** ou as **perguntas**? O gate vai falhar pedindo para regravar. Regrave, **leia o relatório**, e só então ajuste `eval/thresholds.json`, explicando no PR.
- [ ] Mudou um **preço**? Altere o `plans.json` **e** o `planos.md` (um teste barra a divergência) e regrave o cassete.
- [ ] O piso só **sobe** sem justificativa. Para baixar, explique o motivo no PR.
- [ ] Nova pergunta de avaliação? Vai para **ajuste** se você vai usá-la para corrigir algo; **validação** só se ninguém a olhou antes de ajustar.
- [ ] Mexeu em `Dockerfile`, `.dockerignore` ou `docker-compose.yml`? `tests/test_container.py` confere o que dá sem Docker; **construa a imagem** e rode a lista "a verificar" do caderno 09.
- [ ] Atualizou um caderno de `docs/aprendizado` se o comportamento mudou.

## 4. O que cada trava protege (e o que NÃO protege)

| trava | protege contra | **não** protege contra |
|---|---|---|
| hook + CI + gitleaks + push protection | chave, CPF, telefone, IP, caminho de servidor no repo público | segredo em formato que as regras não conhecem (o gitleaks e o GitHub cobrem parte) |
| isolamento por loja (filtro antes da similaridade, BM25 por loja) | pergunta da loja A ver trecho da loja B | erro na hora de **escrever** a base de uma loja |
| limiar de similaridade (0,60) | perguntas totalmente alheias | perguntas **vizinhas** ("quanto custa um corte?"), que pontuam alto |
| regra `suficiente` do modelo | perguntas vizinhas sem base | o modelo errar a regra (não é determinístico) |
| fonte obrigatória e validada | resposta sem lastro | resposta citando fonte real mas dizendo algo que ela não diz |
| checagem de números | valor, dia ou quantidade inventados; confirmação de preço falso | afirmação **sem número** ("tem suporte 24h"); número por extenso |
| escape dos trechos | texto da base fechando a marca e virando instrução | injeção na **pergunta** que o modelo decida obedecer (mitigada pelas regras, não eliminada) |
| limites da API (IP, teto diário, corpo, prazo) | esgotar a cota do Gemini, corpo gigante, thread presa | ataque distribuído por muitos IPs reais; **instância reiniciada zera os contadores** |
| container endurecido | invasor com root, escrita no disco, escalada de privilégio | segredo mal configurado no servidor; tráfego direto à porta (o proxy deve ser o único caminho) |
| gate com cassete | piorar o **código** | o Gemini mudar de comportamento (regrave de tempos em tempos) |

## 5. Números de referência (16/10/2026)

| medida | valor |
|---|---|
| testes automatizados | 200, sem rede |
| busca (25 perguntas): significado / palavras / híbrida | 88% / 72% / 88% no acerto@1; 96% / 88% / **100%** no acerto@3 |
| respostas, ajuste | **20/20** |
| respostas, validação | **25/26** (falha conhecida: v20, "personalizar cores e logo") |
| respostas que inventaram número | 0 |
| manipulações que passaram | 0 |

## 6. Limites conhecidos (mantenha atualizado)

1. **Poucas perguntas** (46 de resposta, 25 de busca): cada uma vale vários pontos percentuais.
2. **As perguntas e os gabaritos são meus**, não de clientes reais.
3. **v20** falha: palavras repetidas em vários chunks deixam o BM25 sem destaque e a busca por significado não acerta. Hipótese descartada: "listas longas diluem o vetor" (6 perguntas sobre outros itens da mesma lista passaram).
4. **Agenda ao vivo** (horário disponível) não existe: a base é só texto público. Seria uma ferramenta que consulta a API pública do Sir Barber (ainda não construída).
4b. **Não há demo hospedada.** Detalhes e o que faltaria para publicar com segurança estão no caderno 10.
5. O assistente só conhece a base **`platform`**; a base de uma barbearia específica ainda não foi escrita.
6. O gate prova que o **código** não piorou; regravar o cassete é o que mostra se o **Gemini** mudou.

## 7. Glossário

- **Chunk:** pedaço da base que vira uma unidade de busca.
- **Embedding:** lista de números que representa o significado de um texto.
- **Cosseno:** medida de proximidade entre dois embeddings (1 = mesmo sentido).
- **BM25:** busca por palavras exatas, com peso maior para palavras raras.
- **RRF:** junta dois rankings somando 1/(60 + posição); usa só a posição.
- **Acerto@k / MRR:** o chunk certo está entre os k primeiros / média de 1/posição do primeiro certo.
- **Cassete:** respostas da API gravadas para reproduzir testes sem rede.
- **Gate:** teste do CI que quebra o build se a qualidade cair abaixo do piso.
- **Prompt injection:** texto que tenta fazer o modelo desobedecer às regras.
- **Tenant (loja):** uma barbearia; os dados de uma nunca podem aparecer para outra.

## 8. Como explicar o projeto em 30 segundos

"Assistente RAG multi-loja em Python sobre o meu SaaS: busca híbrida com BM25 e embeddings, ferramenta determinística para o que exige conta, checagem por código de que todo valor da resposta existe nos trechos, e avaliação em conjuntos separados de ajuste e validação, com um gate no CI feito com respostas gravadas. Documentei o que **não** funciona também: uma pergunta falha na validação e eu diagnostiquei a causa em vez de ajustar o sistema a ela."

## 9. Auditoria de segurança do repositório público (16/10/2026)

Repetir antes de qualquer mudança de visibilidade, de divulgar o link ou de grandes mudanças.

| verificação | como | resultado |
|---|---|---|
| A chave real aparece em algum commit? | `git grep -F "<chave>"` em cada commit de `git rev-list --all` (sem imprimir a chave) | **0 de 15 commits** |
| Algum `.env` ou arquivo de chave já foi commitado (mesmo apagado depois)? | `git log --all --name-only` filtrando `.env`, `.pem`, `.key`, `id_*` | nenhum |
| Detector do projeto no histórico inteiro | `git log --all -p` passado por `scan_text` | 2 achados, ambos **falsos positivos**: um modelo de teste com valor falso montado em tempo de execução |
| Alertas do GitHub (secret scanning) | `gh api repos/<repo>/secret-scanning/alerts` | 0 |
| E-mail pessoal nos commits | `git log --all --format='%ae %ce'` | só o e-mail *noreply* |
| Dados pessoais no texto (usuário do Windows, nome, e-mail) | `git grep` | nenhum |
| A base de conhecimento tem algo que não é público? | cada recurso e preço comparado com `GET /saas/plans` do site, **sem login** | **tudo já é público** |
| O repositório privado do Sir Barber é citado? | `git grep` por caminhos e nome do repositório | 1 caminho de arquivo em um caderno (corrigido); a regra "referência ao repositório privado" do detector agora impede que volte |
| Cassete | busca por `AIza`, `api_key`, `x-goog` + `check_secrets` | limpo; só texto público e vetores |

**Camadas ativas:** hook de pre-commit, CI com gitleaks no histórico, *secret scanning* e *push protection* do GitHub, `main` protegida (só PR com CI verde), Dependabot.

**Riscos que a auditoria NÃO elimina** (para tratar nas etapas de API e demo):
- A **chave do Gemini** na demo: ficará só em variável de ambiente do servidor; abuso da cota gratuita exige limite por IP e teto diário.
- A **API pública** vai receber texto de qualquer pessoa: limite de tamanho, sem registrar o texto da pergunta nem o IP completo.
- Se um dia a chave vazar: revogar no Google AI Studio e criar outra; reescrever o histórico do git **não basta**, porque a chave já estaria copiada.
