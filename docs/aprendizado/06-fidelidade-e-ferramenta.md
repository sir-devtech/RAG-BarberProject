# Etapa 6 — Números verificados por código e ferramenta de cálculo

## O que foi feito
- `app/generation/fidelity.py`: extrai os números da resposta e confere se cada um existe no contexto. Se não, o modelo ganha **uma** correção; se insistir, a resposta é recusada (`numero_nao_fundamentado`).
- `app/tools/plans.py` + `knowledge/platform/plans.json`: dado o número de barbeiros, calcula quais planos servem e entrega o resultado como um **trecho a mais** (fonte `ferramenta:planos`).
- `answer.py`: o resultado da ferramenta vem primeiro no contexto e dispensa o limiar de similaridade.
- 33 testes novos (120 no total), sem rede.

## Por que a checagem é por código
Pedir "não invente valores" no prompt é um **pedido**, não uma garantia. A checagem roda **depois** do modelo e não depende do comportamento dele: extrai todos os números da resposta (`R$ 1.250,90`, `250`, `15`) e compara por **valor** (250,00 é igual a 250). Número sem base volta ao modelo uma vez, com a lista dos suspeitos; se persistir, o usuário recebe a recusa em vez de um preço errado.

## Por que uma ferramenta
"Quanto custa para 5 barbeiros?" é uma **conta** (5 está na faixa 4–8). Busca por texto não faz conta de forma confiável. Um código determinístico calcula e devolve, por exemplo:
`Simples Média: R$ 250, para 4 a 8 barbeiros, sem cobrança Asaas` e `Completo: a partir de R$ 329, para 1 a 8 barbeiros, com cobrança Asaas`. O resultado entra como trecho, então passa pela **mesma** checagem de números das outras fontes. Um teste garante que o `plans.json` e o texto da base nunca divergem.

**Decisão:** o roteamento é por regra (acha "N barbeiros" na pergunta, em dígitos ou por extenso) e não por *function calling* do modelo. Troca: o modelo escolhendo ferramentas é mais flexível, mas custa uma chamada extra por pergunta (cota gratuita), pode errar a escolha e é difícil de testar sem rede. A regra é grátis, determinística e testada.

## Um buraco que eu mesmo abri (e fechei)
Na primeira versão, números **da pergunta** eram aceitos na resposta (necessário para "para 5 barbeiros"). Mas assim, a pergunta "o plano Solo custa R$ 99, certo?" permitiria o modelo responder "Sim, custa R$ 99": o 99 viria da pergunta e passaria. Corrigi: **valores em R$ só valem se estiverem nos trechos**; só quantidades (barbeiros, dias) podem ser repetidas da pergunta. Teste de regressão cobre isso.

## Resultado ao vivo (12 perguntas ao Gemini)
- "5 barbeiros" → Simples Média R$ 250 **e** Completo a partir de R$ 329 (ferramenta). "9 barbeiros" → Simples Grande R$ 350 e Premium a partir de R$ 650.
- "tenho 20 barbeiros" → "nenhum plano atende, os planos vão até 12".
- **Premissa falsa é corrigida:** "o plano Solo custa R$ 99, certo?" → "Não, o plano custa R$ 120 por mês"; "o Premium não custa R$ 100?" → "Não, a partir de R$ 650".
- Recusa quando falta base: "preço por ano do Completo", "plano mais barato de graça".

## O que ainda não está provado
- A checagem pega **números**, não **afirmações**: o modelo poderia dizer "o Completo tem suporte 24 horas" (sem número) e passaria. Mitiga-se com o contexto fechado e a exigência de fonte, mas não é garantido.
- Números por extenso ("três") não são verificados.
- A ferramenta só entende "N barbeiros/profissionais/…"; perguntas como "somos uma equipe pequena" caem na busca normal.
- Continua sem avaliação **em escala** das respostas (etapa 7).

## Alternativas descartadas
- **Function calling do Gemini:** descrito acima.
- **Confiar na instrução do prompt:** não verificável.

## Como explicar na entrevista (2 frases)
"Depois do modelo respondo por código: todo valor em R$ precisa estar nos trechos recuperados (a pergunta não vale, senão o cliente poderia induzir o modelo a confirmar um preço falso), com uma correção e depois recusa. E para o que é conta, como 'quanto custa para 5 barbeiros?', uso uma ferramenta determinística em vez de pedir ao modelo para calcular."

## Perguntas para você responder com as suas palavras
1. Por que um valor em R$ da pergunta do cliente não pode justificar o mesmo valor na resposta?
2. Por que "5 barbeiros" é melhor resolvido por uma ferramenta do que pela busca?
3. Cite um tipo de erro que a checagem de números **não** pega.
