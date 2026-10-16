# Etapa 4 — Busca por palavras, busca híbrida e avaliação

## O que foi feito
- `app/retrieval/text.py`: normalização para português (minúsculas, sem acento, sem palavras comuns, plural simples; números ficam inteiros).
- `app/retrieval/bm25.py`: **BM25 escrito à mão**, com um corpus (e portanto um IDF) por loja.
- `app/retrieval/hybrid.py`: fusão por RRF e a regra de quando o BM25 pode entrar.
- `eval/`: 25 perguntas com gabarito, métricas (acerto@1, acerto@3, MRR) e `run_eval.py` que compara as buscas.
- 25 testes novos (66 no total), todos sem rede.

## Conceito: BM25
Pontua cada chunk, para cada palavra da pergunta, com: **frequência** (quantas vezes aparece, com retorno decrescente), **raridade** (IDF: palavra que está em todo chunk quase não vale) e **tamanho** (chunk curto que tem a palavra vale mais que um longo). É exato: "250" só casa com o chunk que contém "250".

## Conceito: RRF (Reciprocal Rank Fusion)
Cosseno e BM25 têm escalas diferentes, então não se somam. O RRF usa só a **posição**: cada lista dá `1/(60 + posição)`. Quem está bem nas duas sobe.

## A avaliação (o que mais importa)
Métricas: **acerto@1** (o chunk certo é o 1º), **acerto@3** (está entre os 3 primeiros) e **MRR** (média de 1/posição do primeiro certo).

| busca | acerto@1 | acerto@3 | MRR | parafrases @1 / @3 |
|---|---|---|---|---|
| significado (embeddings) | 88% | 96% | 0,92 | 83% / 100% |
| palavras (BM25) | 72% | 88% | 0,79 | 17% / 67% |
| híbrida, RRF sempre | 84% | 96% | 0,90 | 50% / 83% |
| **híbrida adotada** (confiante + concordante) | **88%** | **100%** | **0,94** | 67% / 100% |

"Parafrases" são 6 perguntas **sem nenhuma palavra em comum** com a resposta, como "dá pra desistir sem pagar nada?".

## O que a avaliação ensinou (3 surpresas)
1. **A primeira versão do teste era fácil demais.** Com 19 perguntas "normais", a híbrida parecia ótima (95%/100%), mas o BM25 acertava só porque a pergunta repetia palavras da base ("multa", "quiser"). Ao incluir parafrases, a conta mudou. Um conjunto de teste otimista esconde o defeito.
2. **Fundir sempre piora as parafrases** (de 83% para 50% no acerto@1). O BM25 devolve chunks fracos que casam por palavras comuns ("valor", "começar"), e no RRF posições vizinhas valem quase o mesmo (1/61 contra 1/62), então qualquer apoio da outra lista decide o desempate.
3. **Dar menos peso ao BM25 não resolve.** Entre peso 1,0 e 0,2 o resultado foi idêntico; só com peso próximo de zero ele deixa de atrapalhar (e aí deixa de ajudar).

## A solução adotada
O significado é a base. O BM25 só entra na fusão se **as duas condições** forem verdadeiras:
- **Confiante:** o 1º dele vale pelo menos 1,5× o 2º (ou é o único que casou). "R$ 250" casa com um chunk só; palavras comuns casam com vários de pontuação parecida.
- **Concordante:** o 1º dele está entre os 5 primeiros do significado. A pontuação sozinha não separa um acerto de um erro (um resultado único errado pontuou 2,58; um único certo, 2,74). O significado separa.

Resultado: o BM25 resgata palavras raras e valores exatos (ex.: "tem controle de inadimplência?" passou de fora do top-3 para 1º), sem arrastar chunks sem relação.

## Ressalva honesta
O conjunto tem 25 perguntas (6 parafrases): cada diferença acima equivale a **uma pergunta**. É um indício, não uma prova. Também escolhi a regra olhando estes mesmos números, o que favorece o resultado. Na etapa 7 vamos ampliar o conjunto, separar perguntas que não usei para ajustar e fixar uma meta no CI.

## Pendências assumidas
- **Conteúdo repetido na base** (cancelamento e "trabalha sozinho" estão em dois arquivos): ainda não medimos o efeito de remover.
- **"quanto custa para 5 barbeiros?"** continua errando em todas as buscas: exige conta (faixa 4–8) e vai ser resolvido por uma ferramenta, na etapa 6.

## Alternativas descartadas
- **Biblioteca `rank-bm25`:** funciona, mas é pouco mantida e esconde a fórmula; escrever à mão (≈40 linhas) permite explicar cada termo.
- **Peso fixo no RRF:** testado, não resolveu.

## Como explicar na entrevista (2 frases)
"Medi três buscas num conjunto com parafrases e descobri que fundir embeddings e BM25 sempre piora as perguntas sem palavras em comum; então uso o BM25 só quando ele é confiante e concorda com o significado, o que subiu o acerto@3 de 96% para 100%. Tenho consciência de que são 25 perguntas, por isso a próxima etapa amplia e separa um conjunto de validação."

## Perguntas para você responder com as suas palavras
1. Por que o RRF usa a posição e não a pontuação de cada busca?
2. Por que o primeiro conjunto de perguntas dava uma impressão enganosa da busca híbrida?
3. Por que "o BM25 concorda com o significado" é uma condição melhor que olhar só a pontuação do BM25?
