"""Ponto de entrada do servidor: `python -m app.api.serve`.

Existe para que as opcoes de seguranca do uvicorn nao dependam de alguem lembrar flags:
- proxy_headers=False: o uvicorn, por padrao, confia em X-Forwarded-For de quem vem de
  127.0.0.1 e REESCREVE o IP do cliente. Quem decide em qual cabecalho confiar e a nossa
  configuracao (CLIENT_IP_HEADER), e so ela. Sem isto, qualquer um burlaria o limite por IP.
- access_log=False: o log de acesso do uvicorn imprime o IP de cada visitante; o log
  estruturado da aplicacao (app.api.main) ja registra o necessario, com o IP em hash.
- server_header=False: nao anunciar qual software responde.
"""

from __future__ import annotations

import os
import re

import uvicorn

HOST = re.compile(r"^[0-9a-zA-Z.:-]{1,64}$")


def serve_options(env: dict[str, str] | None = None) -> dict[str, object]:
    source = env if env is not None else dict(os.environ)
    host = source.get("HOST", "127.0.0.1").strip()  # padrao local: expor e uma decisao consciente
    if not HOST.fullmatch(host):
        raise ValueError("HOST invalido")
    try:
        port = int(source.get("PORT", "8000"))
    except ValueError:
        raise ValueError("PORT deve ser um numero") from None
    if not 1 <= port <= 65535:
        raise ValueError("PORT fora do intervalo")
    return {
        "app": "app.api.main:build_app",
        "factory": True,
        "host": host,
        "port": port,
        "proxy_headers": False,
        "server_header": False,
        "access_log": False,
    }


def main() -> None:
    uvicorn.run(**serve_options())  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
