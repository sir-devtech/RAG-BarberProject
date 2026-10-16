# Etapa 3 — Embeddings e busca por significado

## O que foi feito
- `app/ingest/embeddings.py`: cliente do Gemini (modelo `gemini-embedding-001`, 768 números por texto) com **retentativa** em 429/500/502/503/504 e **cache** em disco por hash do texto.
- `app/ingest/index.py`: gera os vetores de uma lista de chunks, chamando a API só para o que é novo ou mudou.
- `app/retrieval/dense.py`: índice que compara a pergunta com os chunks por **similaridade de cosseno**.
- `scripts/ask_dense.py`: faz perguntas na base usando só essa busca.
- `app/config.py`: agora lê o `.env` (variáveis do ambiente têm prioridade, para servidor e CI).
- 16 testes novos (41 no total), todos **sem rede**, com um Gemini simulado.

## Conceito
Um modelo de embedding lê um texto e devolve uma lista de números: as **coordenadas do significado**. Textos de sentido parecido ficam em coordenadas próximas, mesmo sem palavras em comum. A **similaridade de cosseno** mede o ângulo entre dois vetores (1 = mesma direção). Com todos os vetores normalizados (tamanho 1), ela vira um produto escalar, que o numpy calcula para a base inteira de uma vez.

Dois detalhes que importam:
- **Tarefas diferentes:** documentos são embutidos com `RETRIEVAL_DOCUMENT` e perguntas com `RETRIEVAL_QUERY`. O modelo ajusta o vetor ao papel de cada texto.
- **Normalizar:** com 768 dimensões a API não normaliza, então fazemos isso no código.

## Decisões
1. **Filtro por loja antes da comparação.** O índice só compara com chunks da loja pedida. Um teste coloca um chunk da loja B **idêntico à pergunta** e confirma que ele nunca aparece para a loja A.
2. **Retentativa com espera crescente (1, 2, 4, 8 s)** só para erros temporários. Erro 400 não é repetido. Vimos 503 de verdade ao testar os modelos, então isso não é teoria.
3. **A chave vai no cabeçalho, nunca na URL**, e mensagens de erro trocam a chave por `<chave>`. Teste confirma.
4. **Cache por hash do texto + modelo + dimensões.** Mudar uma frase refaz só aquele chunk. A escrita é atômica (arquivo temporário e troca), então um erro no meio não deixa o cache pela metade.

## O experimento: onde a busca por significado acerta e erra
Rodei 8 perguntas na base real (22 chunks). Resultados:

| Pergunta | Chunk certo | Veredito |
|---|---|---|
| "posso desmarcar quando quiser?" | 1º (0,753) | **Acerta por sinônimo** (não existe a palavra "desmarcar" na base) |
| "tem multa se eu sair?" | 1º (0,744) | **Acerta por sinônimo** |
| "o pix libera o teste grátis?" | 1º (0,817) | Acerta, com folga |
| "qual o preço do Simples Média?" | 1º (0,800) | Acerta, com folga |
| "quanto custa para 3 barbeiros?" | 1º (0,754) | Acerta **por pouco**: 2º (0,749) e 3º (0,740) são de 1 barbeiro |
| "R$ 250" | 1º (0,670) | Acerta, mas fraco: R$ 350 e R$ 120 vêm logo atrás |
| "qual plano tem WhatsApp?" | 1º (0,642) | Quase empate com chunks sem relação (0,634 e 0,631) |
| "quanto custa para 5 barbeiros?" | **2º** (0,735) | **ERRA**: o 1º é "1 barbeiro, R$ 120" |

## O que isso ensina
1. **Sinônimos são o ponto forte.** Foi o que eu chamei de "desmarcar ≈ cancelamento".
2. **Números e nomes exatos são o ponto fraco.** O modelo vê "R$ 250" e "R$ 350" como quase a mesma coisa. Uma busca por palavras exatas (BM25, etapa 4) resolve isso.
3. **Conta não é busca.** "5 barbeiros" precisa da lógica "5 está na faixa de 4 a 8, então Simples Média". Nenhuma busca por texto faz isso de forma confiável. Esse caso pede uma **ferramenta** que calcula o plano certo (etapa 6).
4. **As pontuações ficam espremidas** (0,63 a 0,82). Um corte fixo, como "abaixo de 0,7 responde 'não sei'", é frágil. Vamos calibrar com a avaliação, não no chute.
5. **Conteúdo repetido gasta vaga do top-3.** "Cancelar" e "trabalhar sozinho" aparecem em dois arquivos, então ocupam duas das três vagas com a mesma informação. Vamos remover as repetições e **medir** a melhora.

## Alternativas descartadas
- **Banco vetorial (Pinecone, pgvector):** para 22 chunks é exagero e custa. `numpy` resolve e é fácil de explicar.
- **Só busca por palavras-chave:** perde "desmarcar", "multa", "sair".

## Como explicar na entrevista (2 frases)
"Testei a busca densa com perguntas reais e vi que ela acerta sinônimos, mas erra números e faixas, como 'quanto custa para 5 barbeiros?'. Por isso combino com busca por palavras exatas e uso uma ferramenta para o que exige cálculo."

## Perguntas para você responder com as suas palavras
1. Por que uma pergunta e um documento são embutidos com tarefas diferentes?
2. Por que "quanto custa para 5 barbeiros?" falha mesmo com um bom modelo de embedding?
3. Por que o filtro por loja acontece antes de calcular as similaridades?
