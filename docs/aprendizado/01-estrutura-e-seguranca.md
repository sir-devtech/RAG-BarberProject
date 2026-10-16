# Etapa 1 — Estrutura, CI e proteção contra vazamento

## O que foi feito
- Esqueleto do projeto: `app/` (código), `tests/`, `scripts/`, `knowledge/` (base de conhecimento), `eval/`.
- `pyproject.toml` com ferramentas de qualidade: **ruff** (estilo/erros), **mypy** em modo estrito (tipos), **pytest** (testes).
- `app/config.py`: lê a configuração do ambiente; nunca guarda valor secreto no código.
- `scripts/check_secrets.py` + `.githooks/pre-commit`: barram segredo e dado pessoal **antes** do commit.
- `.github/workflows/ci.yml`: roda tudo isso no GitHub a cada push/PR, mais o gitleaks no histórico inteiro.

## Por que
O repositório é **público**. Qualquer coisa commitada fica visível e **permanece no histórico do git mesmo se for apagada depois**. Por isso a proteção vem antes do primeiro código de verdade: é bem mais barato impedir um vazamento do que limpar um (e uma chave vazada precisa ser revogada de qualquer jeito).

## Como funciona
1. `.gitignore` ignora `.env`: a chave fica só no seu computador. O `.env.example` mostra quais variáveis existem, sem valores.
2. O hook `pre-commit` roda `check_secrets.py --staged` e, se achar algo, **cancela o commit**. Ele procura: chave Gemini, token GitHub, chave privada, CPF, telefone, IP, caminho de servidor, nome de chave SSH e e-mail pessoal. O relatório mostra arquivo, linha e tipo, **nunca o valor**.
3. No CI o mesmo script roda em todos os arquivos, e o gitleaks examina o histórico completo.
4. O GitHub tem ainda o *push protection*, que recusa o push se reconhecer uma chave conhecida.
5. `Settings.__repr__` omite a chave: se alguém imprimir o objeto num log ou erro, ela não aparece.

## Alternativas descartadas
- **Só o gitleaks:** não conhece as regras do projeto (telefone, caminho do servidor, IP). Usamos os dois.
- **Hook sem CI:** o hook é local e pode ser pulado (`--no-verify`). O CI não pode.

## Como explicar na entrevista (2 frases)
"Como o repositório é público, coloquei três camadas contra vazamento antes de escrever a lógica: hook de pre-commit com regras do projeto, gitleaks no CI sobre o histórico e o push protection do GitHub. A configuração vem do ambiente e o objeto de settings nem imprime a chave."

## Perguntas para você responder com as suas palavras
1. Por que apagar uma chave num commit novo não resolve o vazamento?
2. Qual a diferença entre o hook de pre-commit e a checagem do CI, e por que ter as duas?
3. Por que o relatório do detector nunca mostra o trecho encontrado?
