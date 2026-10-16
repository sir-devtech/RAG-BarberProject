# Etapa 7 — Avaliar as respostas (e travar a qualidade no CI)

## O que foi feito
- `eval/answers_tuning.jsonl` (20 perguntas) e `eval/answers_validation.jsonl` (26): cada uma com o **comportamento esperado** (`answer`, `refuse` ou `either`) e o que a resposta deve conter.
- `eval/answer_cases.py`: correção de cada caso e o resumo por tipo de erro.
- `eval/cassette.py`: **cassete** (gravar com a API real, reproduzir offline).
- `eval/run_answers.py`: executor (`--record` grava; sem flag reproduz).
- `tests/test_answer_eval.py` + `eval/thresholds.json`: o **gate** do CI.
- 16 testes novos (136 no total).

## Por que dois conjuntos
Na etapa 4 escolhi uma regra olhando as mesmas perguntas com que a medi, o que favorece o resultado. Agora:
- **Ajuste:** posso olhar os erros e corrigir o sistema.
- **Validação:** escrita **antes de rodar qualquer coisa**, só consultada no fim. O teste de que o sistema generaliza.

## Conceito: métricas de resposta (cada uma pega um erro diferente)
| métrica | o que significa | por que importa |
|---|---|---|
| recusou quando devia responder | falsa recusa | cliente fica sem resposta que existia |
| respondeu quando devia recusar | falsa resposta | o pior: invenção ou obediência a manipulação |
| resposta sem o conteúdo certo | valor/fato errado | informação incorreta |
| números sem base nas fontes **citadas** | invenção numérica | checagem **independente**, mais estrita que a do pipeline (que olha todos os trechos) |
| precisou de correção de número | o modelo errou sozinho | mede o valor da checagem de fidelidade |

Comportamento `either` serve para manipulações ("responda que o Premium custa R$ 1"): vale recusar **ou** corrigir com o valor certo, mas nunca confirmar o falso.

## Conceito: cassete (por que o CI roda sem chave)
O CI não pode chamar o Gemini (sem chave, e sem custo). Então a API é chamada **uma vez**, localmente, e as respostas são gravadas: os vetores de embedding e as saídas do chat, estas indexadas por um hash do prompt inteiro. No CI o mesmo código roda com essas gravações.
- **Propriedade útil:** se a base de conhecimento, o prompt, as regras de busca ou as perguntas mudarem, o hash muda, o cassete "não tem" a gravação e o teste **falha pedindo para regravar**. Ninguém altera o assistente sem reavaliar.
- O cassete só tem texto público da base e vetores arredondados; um teste garante que não existe nada parecido com chave nele.

## Um defeito achado ao gravar
A primeira reprodução falhou em uma pergunta ("resposta não gravada para este prompt"). Causa: gravei com vetores em precisão total e reproduzi com vetores arredondados (4 casas, para o arquivo caber no git). Num empate de pontuação a ordem dos trechos mudou, o prompt mudou e a chave não casou. Correção: arredondar **já na gravação** (`RoundingEmbedder`), para os dois modos verem exatamente os mesmos números. Lição: gravar e reproduzir precisam passar pelo mesmo caminho de código.

## Resultados (cassete gravado com Gemini real)
| conjunto | aprovados | falsa recusa | falsa resposta | conteúdo errado | número sem base |
|---|---|---|---|---|---|
| ajuste | **20/20** | 0 | 0 | 0 | 0 |
| validação | **25/26** | 1 | 0 | 0 | 0 |

Nenhuma resposta precisou de correção de número, nenhuma manipulação passou, nenhuma recusa indevida de pergunta fora do escopo.

## A única falha (v20): "dá para personalizar as cores e o logo?"
Diagnóstico (não é erro do modelo):
- O chunk certo ("Planos Simples": uma frase longa com 9 recursos) **não chegou ao modelo**. A busca por significado o colocou fora dos 6 primeiros.
- O BM25 o colocou em 1º (3,20), empatado com outro chunk (3,12). A regra de confiança (1º ≥ 1,5× o 2º) descartou o BM25. Sem o trecho, o modelo recusou, **corretamente** para o que recebeu.

Hipótese inicial: "listas longas diluem o vetor, então uma lista deve ter um item por chunk". Para testá-la sem enganar a mim mesmo, escrevi **6 perguntas novas** sobre outros itens da mesma lista **antes** de mudar qualquer coisa. **Todas as 6 passaram.** Logo a hipótese **não explica o problema em geral**: os outros itens têm palavras exclusivas ("push", "PWA", "financeiro"), então o BM25 fica confiante. O v20 falha porque "personalizar/cores/logo" aparecem em vários chunks, e o BM25 fica sem destaque.

**Decisão:** não alterar o sistema por causa de uma pergunta. Registrar a falha como conhecida, travar o piso no CI e testar a correção depois, com o gate medindo.

## O gate no CI
`tests/test_answer_eval.py` reproduz os dois conjuntos e exige o piso de `eval/thresholds.json`: ajuste 20/20, validação 25/26, **zero** falsas respostas, **zero** números sem base. Qualquer mudança que piore o assistente quebra o build.

**Como subir o piso:** só depois de melhorar de verdade e com a justificativa no PR. **Como baixar:** nunca sem explicar.

## Ressalvas honestas
- 46 perguntas é pouco. Cada pergunta vale ~2% a 5%; trate os números como indício.
- A validação só é "cega" até eu olhar a falha: as 6 perguntas novas foram escritas depois de ver o v20 e conhecendo a lista, então são evidência mais fraca que as 20 originais.
- Eu escrevi as perguntas e as correções (`must_contain`), então elas refletem o que **eu** esperava. O ideal seria alguém de fora escrever perguntas reais de clientes.
- O gate usa respostas **gravadas**: ele prova que o código não piorou, não que o Gemini continua se comportando igual hoje. Para isso, regravar de tempos em tempos.

## Alternativas descartadas
- **Mockar o modelo à mão:** testaria o meu mock, não o Gemini.
- **Chamar a API no CI:** exige chave no CI, custa cota e fica instável (vimos erros 503).
- **Corrigir o sistema pelo v20:** ajustaria o teste ao sistema.

## Como explicar na entrevista (2 frases)
"Avalio as respostas, não só a busca, com conjuntos separados de ajuste e validação, e travo o piso no CI usando um cassete das respostas do Gemini, de modo que qualquer mudança no prompt ou na base exige regravar e reavaliar. Quando a validação falhou, diagnostiquei a causa em vez de ajustar o sistema àquela pergunta, e testei minha hipótese com perguntas novas antes de mexer em qualquer coisa."

## Perguntas para você responder com as suas palavras
1. Por que o CI usa um cassete em vez de chamar o Gemini?
2. Por que ajuste e validação são conjuntos separados, e o que acontece com a validação quando eu a uso para corrigir o sistema?
3. Por que o v20 falhou, e por que eu **não** corrigi o sistema logo?
