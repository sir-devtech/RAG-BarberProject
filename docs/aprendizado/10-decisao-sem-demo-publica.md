# Etapa 10 — Fechamento: por que não há demo pública

## O que foi decidido
Não publicar uma demo ao vivo. Em vez disso: **modo de demonstração offline** (`python -m scripts.demo`), **roteiro de vídeo** e documentação do que foi medido. Decisão do dono do projeto, tomada depois de olhar o custo e o risco.

## Como se chegou a isso (as opções foram verificadas, não supostas)
O plano original colocava a demo no servidor onde o Sir Barber roda. Antes de qualquer mudança, uma leitura **somente de consulta** do servidor mostrou:

- **Pouca memória livre** (menos de 150 MB) e uso de swap já em andamento. Um container extra, mesmo pequeno, podia levar o Linux a **encerrar um processo** para se recuperar, e os candidatos eram a API ou o banco do Sir Barber.
- O proxy (nginx) que atende o Sir Barber é configurado no mesmo conjunto de arquivos; um subdomínio novo exigiria **mexer na configuração que serve a produção**.

Conclusão: **o risco para o sistema que importa era maior que o benefício de uma demo de portfólio**. O custo de redimensionar o servidor também contrariava o pedido de custo zero.

A segunda opção foi a plataforma de hospedagem Hugging Face Spaces. Eu tinha dito, de memória, que seria gratuita. Ao conferir a **documentação oficial e a página de preços**, descobri que criar um Space que roda código (Docker) **exige um plano pago (US$ 9/mês)**; só Spaces estáticos são grátis. Corrigi a informação antes de o dono do projeto assinar qualquer coisa.

> **Lição:** valores e limites de serviços mudam; confirme na fonte oficial antes de recomendar, e corrija em voz alta quando estiver errado.

## O que ficou no lugar
| entrega | para quê |
|---|---|
| `python -m scripts.demo` | roda 9 cenas **sem chave e sem internet**, a partir do cassete; qualquer pessoa reproduz |
| `docs/ROTEIRO_DO_VIDEO.md` | roteiro com narração, lista de privacidade e o que **não** dizer |
| imagem Docker verificada | prova de que o serviço roda isolado; quem quiser sobe com `docker compose up` |
| avaliação e CI | os números ficam reproduzíveis |

A demonstração offline inclui, **de propósito**, uma cena em que o assistente **falha** (a falha conhecida v20). Mostrar o limite dá mais credibilidade do que escondê-lo.

## O que NÃO foi feito (dito de frente)
- **Sem demo hospedada:** ninguém consegue digitar uma pergunta nova sem rodar o projeto.
- **Sem ferramenta de agenda ao vivo** ("tem horário amanhã às 15h?"): o plano original previa consultar a API pública do Sir Barber; ficou de fora.
- **Só a base da plataforma:** nenhuma barbearia específica foi indexada, então o **isolamento entre lojas** é testado por testes unitários, mas não demonstrado com duas lojas reais.
- **Perguntas escritas pelo autor:** falta avaliar com perguntas de clientes de verdade.
- **Falha v20** sem correção, de propósito, para não ajustar o sistema a uma pergunta.
- **Limites da API em memória:** zeram ao reiniciar e não valem para mais de uma instância.

## Se um dia a demo for ao ar
Já está pronto o que dá para preparar: imagem verificada, limites, logs sem dados pessoais e isolamento de container. Faltaria:
1. **Onde:** um servidor com folga de memória, separado do Sir Barber, ou um plano de hospedagem.
2. **O IP do visitante:** atrás de um proxy, configurar `CLIENT_IP_HEADER` com um cabeçalho que o proxy **sobrescreve**. Se a plataforma só **acrescenta** ao `X-Forwarded-For`, o código atual (que lê o primeiro valor) seria enganado; seria preciso ler o último, e **testar contra o servidor real**.
3. **Uma chave separada**, num projeto separado do Google AI Studio, para poder revogá-la sem afetar o resto. (Isso já foi feito neste projeto: existe um projeto "Teste-RAG" reservado para isso.)
4. **Monitoramento** do endereço de saúde.

## Como explicar na entrevista (2 frases)
"Cheguei a planejar a demo no servidor do Sir Barber, mas a leitura do servidor mostrou memória quase esgotada, e eu não ia arriscar a produção por um portfólio; a alternativa hospedada exigia plano pago, então optei por uma demonstração offline reproduzível e um vídeo. Deixei documentado o que faltaria para publicar com segurança."

## Perguntas para você responder com as suas palavras
1. Por que a leitura do servidor, feita **antes** de qualquer mudança, mudou o plano?
2. Por que o `scripts/demo.py` precisa funcionar sem chave e sem internet?
3. Por que mostrar uma falha conhecida no vídeo ajuda, em vez de atrapalhar?
