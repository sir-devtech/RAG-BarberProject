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
.venv\Scripts\python -m eval.run_answers --record      # regrava o cassete (usa a chave e a cota)
```

## 3. Checklist de qualidade (antes de mesclar qualquer PR)

- [ ] `pytest`, `ruff` e `mypy` verdes (o CI repete isso).
- [ ] `check_secrets.py` sem achados e **nenhum** `.env` no commit (o hook barra, confira mesmo assim).
- [ ] Mudou a **base de conhecimento**, o **prompt**, as **regras de busca** ou as **perguntas**? O gate vai falhar pedindo para regravar. Regrave, **leia o relatório**, e só então ajuste `eval/thresholds.json`, explicando no PR.
- [ ] Mudou um **preço**? Altere o `plans.json` **e** o `planos.md` (um teste barra a divergência) e regrave o cassete.
- [ ] O piso só **sobe** sem justificativa. Para baixar, explique o motivo no PR.
- [ ] Nova pergunta de avaliação? Vai para **ajuste** se você vai usá-la para corrigir algo; **validação** só se ninguém a olhou antes de ajustar.
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
| gate com cassete | piorar o **código** | o Gemini mudar de comportamento (regrave de tempos em tempos) |

## 5. Números de referência (16/10/2026)

| medida | valor |
|---|---|
| testes automatizados | 136, sem rede |
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
