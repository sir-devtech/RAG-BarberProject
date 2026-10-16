# Imagem do assistente. Decisoes de seguranca estao comentadas junto de cada linha.
# A base e fixada pelo digest: o mesmo build gera a mesma imagem, e uma tag nao pode ser trocada
# por outra sem voce perceber. Para atualizar: docker buildx imagetools inspect python:3.12-slim
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# Sem .pyc e sem buffer de saida (logs aparecem na hora). PYTHONPATH porque o codigo e
# copiado, nao instalado como pacote: o app acha a pasta knowledge/ pelo caminho do arquivo.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias primeiro: so refaz esta camada quando o pyproject muda.
# A lista vem do proprio pyproject.toml (fonte unica; nada duplicado aqui).
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# So o que a API precisa. Testes, avaliacao, scripts, docs e .env ficam de fora (.dockerignore).
COPY app ./app
COPY knowledge ./knowledge

# Usuario sem privilegios e sem shell de login. /data e o unico lugar gravavel (cache de vetores).
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data && chown app /data
USER app

# Dentro do container escuta em todas as interfaces; quem decide quem alcanca a porta e o
# docker-compose (publica so em 127.0.0.1). A CHAVE nunca e gravada na imagem: vem do ambiente.
ENV HOST=0.0.0.0 \
    PORT=8000 \
    INDEX_DIR=/data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

CMD ["python", "-m", "app.api.serve"]
