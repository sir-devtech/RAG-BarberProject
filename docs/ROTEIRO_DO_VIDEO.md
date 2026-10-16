# Roteiro do vídeo de demonstração (3 a 4 minutos)

Objetivo: mostrar que o assistente **funciona, recusa o que não sabe e foi medido**, sem demo hospedada. Quem assistir deve sair sabendo três coisas: o que ele faz, por que dá para confiar, e onde ainda falha.

## Antes de gravar: privacidade (o mais importante)
O repositório é público e o vídeo também será. Confira **antes** de apertar gravar:

- [ ] **Feche** todas as abas e janelas que não sejam o terminal e o editor (e-mail, LinkedIn, WhatsApp, banco, outras contas).
- [ ] **Nunca abra o `.env`** durante a gravação, nem no Bloco de Notas nem no editor. Ele contém a chave.
- [ ] Antes da cena 4, rode `cls` e confira que o histórico do terminal não mostra a chave. Se você colou a chave em algum comando antes, **abra um terminal novo**.
- [ ] Esconda ou feche notificações (Windows: "Não perturbe"). Uma notificação de e-mail aparece no vídeo.
- [ ] Grave só a janela do terminal, não a tela inteira (barra de tarefas, nome de usuário e outros aplicativos aparecem).
- [ ] Pasta do projeto no caminho do terminal: troque o prompt para algo curto (`PS RAG>`) com `function prompt { "PS RAG> " }` para não mostrar seu nome de usuário do Windows.
- [ ] Assista ao vídeo inteiro **depois de gravar**, antes de publicar, procurando o que não devia aparecer.
- [ ] Hospede como **YouTube "não listado"** (ou Loom/Drive com link), nunca dentro do repositório (arquivo grande e permanente no histórico do git).

## Como gravar no Windows (grátis)
- **Xbox Game Bar:** `Win + G`, botão de gravar (ou `Win + Alt + R`). Grava a janela ativa. Fica em `Vídeos > Capturas`.
- Ou **OBS Studio**, se quiser narrar com mais controle.
- Narre com calma, em português. Não precisa de edição: um take de 3 a 4 minutos com uma ou duas pausas cortadas já basta.

## Roteiro

### Cena 1 — O que é (0:00 a 0:25)
Mostre o README no navegador (só a primeira tela).
> "Este é um assistente em Python que responde dúvidas sobre o Sir Barber, um sistema de agendamento para barbearias que eu criei. Ele usa busca híbrida e o Gemini em nível gratuito, e o ponto principal do projeto é que **ele não inventa preço**."

### Cena 2 — Funcionando, sem chave (0:25 a 2:00)
No terminal:
```bash
cd C:\RAG-BarberProject
.venv\Scripts\python -m scripts.demo
```
Role devagar e comente **cada cena** (a saída já traz o título de cada uma):
1. **"6 barbeiros"**: "Isso é uma conta, e eu não deixo o modelo calcular. Um código descobre que 6 está na faixa de 4 a 8 e entrega o resultado para ele."
2. **Cancelamento**: "Resposta simples, sempre com a fonte."
3. **Premissa falsa ("custa R$ 200, certo?")**: "O cliente afirma um preço errado. Ele corrige, não confirma. Por trás há uma checagem por código: todo valor em reais da resposta precisa estar nos trechos."
4. **Solo "gratuito"**: "Aqui ele corrige o valor, mas **não diz 'não' de forma explícita**. Eu deixo isso à mostra de propósito."
5. **Capital do Brasil**: "Recusa antes de chamar o modelo. Não gasta nem uma chamada."
6. **CNPJ**: "A pergunta parece do assunto, mas a base não tem. Quem recusa é o modelo."
7. **Manipulação** ("ignore as regras…") e **preço falso a R$ 1**: "Não obedece, e a checagem de números impede que ele confirme o valor."
8. **Falha conhecida**: "Esta pergunta ele errou: recusou algo que existe. Eu diagnostiquei o motivo e documentei no caderno 07, em vez de ajustar o sistema para essa pergunta."

### Cena 3 — Como sei que funciona (2:00 a 3:00)
```bash
.venv\Scripts\python -m eval.run_answers --verbose
```
> "Eu avalio as **respostas**, não só a busca, em dois conjuntos separados: um para ajustar e um para validar, que eu escrevi antes de rodar qualquer coisa. No ajuste são 20 de 20; na validação, 25 de 26. O CI roda isso com respostas gravadas, sem chave, e quebra o build se a qualidade cair."

Mostre depois `.venv\Scripts\pytest -q` terminando em verde (200 testes).

### Cena 4 — Pergunta de verdade (3:00 a 3:30, opcional)
Só se tiver conferido a privacidade acima.
```bash
.venv\Scripts\python -m scripts.ask "o plano Solo é gratuito?"
```
> "Aqui já é o Gemini de verdade, com a minha chave, que fica só num arquivo que não vai para o GitHub."

### Cena 5 — Segurança e limites (3:30 a 4:00)
Mostre no navegador `docs/GUIA_DE_ESTUDO_E_QUALIDADE.md`, a tabela "O que cada trava protege (e o que NÃO protege)".
> "O repositório é público, então auditei o histórico inteiro contra vazamento de chave. A API tem limite de uso por IP e um teto diário. E eu documentei o que **não** está provado: são 46 perguntas escritas por mim, e o próximo passo seria usar perguntas de clientes reais."

## Fechamento (para a descrição do vídeo)
> Assistente RAG em Python (busca híbrida BM25 + embeddings, Gemini, FastAPI, Docker) com checagem de números por código, avaliação em conjuntos separados e gate de qualidade no CI. Código e documentação: https://github.com/sir-devtech/RAG-BarberProject

## O que **não** dizer
- Que há uma demo no ar. **Não há**; por isso o vídeo.
- Que há clientes pagantes usando o assistente. Não há.
- Que 25 de 26 prova qualidade geral. São 46 perguntas, escritas por mim.
- Que o modelo "nunca erra". A checagem pega **números**, não toda afirmação.
