# Etapa 2 — Base de conhecimento e chunking

## O que foi feito
- `knowledge/platform/`: 4 arquivos markdown com informação **pública** do Sir Barber (planos e preços, teste grátis, recursos, FAQ). Os valores e os recursos conferem com a lista de planos que o próprio site já serve ao público (rota `/saas/plans`, sem login).
- `app/ingest/chunking.py`: divide um markdown em pedaços (*chunks*).
- `app/ingest/loader.py`: lê `knowledge/<loja>/*.md` e devolve os chunks de **uma** loja.
- `scripts/show_chunks.py`: mostra na tela como a base foi dividida.
- 14 testes novos (25 no total).

## Por que chunking existe
Um modelo de embedding transforma um texto em **um vetor** (uma lista de números que representa o significado). Um vetor só consegue representar bem **uma ideia**.
- Pedaço **grande demais**: o vetor vira uma "média" de vários assuntos e a busca fica imprecisa.
- Pedaço **pequeno demais**: perde o contexto. "custa R$ 160 por mês" sozinho não diz de qual plano é.

## Como funciona (3 decisões)
1. **Corta por títulos.** Cada seção do markdown (`#`, `##`, `###`) vira um chunk. Seção grande é dividida por parágrafos e, se ainda for grande, por frases ou linhas (listas quase não têm ponto final).
2. **Trilha de títulos em cada chunk.** O chunk "Simples Pequena" guarda `Planos e preços do Sir Barber > Simples Pequena` e esse texto vai junto para o embedding. É a decisão mais importante: o preço nunca fica separado do nome do plano. Um teste lê a base real e confere isso para os 6 planos.
3. **Overlap.** Quando uma seção precisa ser dividida, o chunk seguinte **começa repetindo a última unidade** do anterior, para uma ideia cortada no meio aparecer inteira em pelo menos um deles.

## Um erro meu que o teste pegou
Na primeira versão eu agrupava os pedaços até encher e só depois tentava repetir a última unidade. Como o grupo já estava cheio, o overlap **nunca cabia** e o teste falhou. Corrigi: o grupo novo já **nasce** com a unidade repetida e o resto é empacotado em volta. Lição: uma funcionalidade que nunca é testada pode parecer funcionar e não fazer nada.

## Outros cuidados
- **Isolamento por loja desde o início:** `load_tenant_chunks("loja-a")` só lê `knowledge/loja-a/`. O nome da loja vira nome de pasta, então é validado (`../segredo` é recusado). Teste garante que a base da loja A não contém nada da B.
- **IDs estáveis e `content_hash`:** o hash muda só quando o texto muda. Na próxima etapa isso evita pagar (em cota) para refazer embeddings de texto que não mudou.

## Alternativas descartadas
- **Tamanho fixo (ex.: 500 caracteres) ignorando títulos:** corta no meio de uma frase e separa o preço do nome do plano.
- **Um arquivo = um chunk:** simples, mas o vetor mistura todos os planos.

## Como explicar na entrevista (2 frases)
"Dividi a base por seções do markdown e coloquei a trilha de títulos em cada pedaço, porque um valor sem o nome do plano é ambíguo para a busca. Para seções longas uso overlap, e testei com a base real que cada preço fica no mesmo chunk do seu plano."

## Perguntas para você responder com as suas palavras
1. Por que o chunk "R$ 160 por mês" sozinho é um problema para a busca?
2. O que o overlap resolve e qual o custo dele?
3. Por que o nome da loja é validado antes de virar nome de pasta?
