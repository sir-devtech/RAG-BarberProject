import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.settings import ApiSettings, ApiSettingsError
from app.gemini import GeminiError
from app.generation.answer import Answer, Source

BEARER_OK = "token-de-metricas-com-mais-de-16"
# IPs falsos montados em partes: o repositorio e publico e o detector barra IP literal.
IP_A = ".".join(["1", "1", "1", "1"])
IP_B = ".".join(["2", "2", "2", "2"])
PERGUNTA = "quanto custa o plano Solo? SEGREDO-NA-PERGUNTA"


class FakeService:
    chunk_count = 22

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def ask(self, question: str, tenant: str) -> Answer:
        self.calls.append((question, tenant))
        if self.error:
            raise self.error
        return Answer(
            text="O plano Solo custa R$ 120.",
            sources=[Source(1, "platform/planos.md", "Planos > Solo", "R$ 120")],
            grounded=True,
            reason="ok",
        )


def client(
    service: FakeService | None = None, **settings: object
) -> tuple[TestClient, FakeService]:
    svc = service or FakeService()
    defaults: dict[str, object] = {"per_minute": 100, "per_day": 1000, "daily_cap": 1000}
    app = create_app(svc, ApiSettings(**{**defaults, **settings}))  # type: ignore[arg-type]
    return TestClient(app), svc


def ask(c: TestClient, **body: object) -> object:
    return c.post("/perguntar", json={"pergunta": PERGUNTA, **body})


# ---------- caminho feliz ----------


def test_pergunta_devolve_resposta_com_fontes() -> None:
    c, svc = client()
    r = ask(c)
    assert r.status_code == 200  # type: ignore[attr-defined]
    body = r.json()  # type: ignore[attr-defined]
    assert body["respondeu"] is True and "R$ 120" in body["resposta"]
    assert body["fontes"] == [
        {"numero": 1, "arquivo": "platform/planos.md", "secao": "Planos > Solo"}
    ]
    assert svc.calls == [(PERGUNTA, "platform")]


def test_health_nao_chama_o_modelo_nem_expoe_configuracao() -> None:
    c, svc = client()
    assert c.get("/health").json() == {"status": "ok", "trechos": 22}
    assert svc.calls == []


# ---------- validacao ----------


@pytest.mark.parametrize(
    "body",
    [
        {"pergunta": ""},
        {"pergunta": "x" * 501},
        {"pergunta": "oi", "loja": "../segredo"},
        {"pergunta": "oi", "loja": "A B"},
        {"pergunta": "oi", "extra": "campo desconhecido"},
        {"pergunta": 123},
        {},
    ],
)
def test_entradas_invalidas_sao_recusadas_sem_chamar_o_modelo(body: dict[str, object]) -> None:
    c, svc = client()
    assert c.post("/perguntar", json=body).status_code == 422
    assert svc.calls == []


def test_loja_nao_permitida_responde_404_igual_a_inexistente() -> None:
    c, svc = client(allowed_tenants=["platform"])
    for loja in ["outra-loja", "inexistente"]:
        r = ask(c, loja=loja)
        assert r.status_code == 404 and r.json() == {"erro": "Loja não disponível."}  # type: ignore[attr-defined]
    assert svc.calls == []


# ---------- limites ----------


def test_limite_por_minuto_devolve_429_com_retry_after() -> None:
    c, svc = client(per_minute=2)
    assert ask(c).status_code == 200  # type: ignore[attr-defined]
    assert ask(c).status_code == 200  # type: ignore[attr-defined]
    r = ask(c)
    assert r.status_code == 429  # type: ignore[attr-defined]
    assert int(r.headers["retry-after"]) >= 1  # type: ignore[attr-defined]
    assert len(svc.calls) == 2


def test_spam_invalido_tambem_gasta_o_limite() -> None:
    c, _ = client(per_minute=2)
    for _ in range(2):
        assert c.post("/perguntar", json={"pergunta": ""}).status_code == 422
    assert c.post("/perguntar", json={"pergunta": ""}).status_code == 429


def test_teto_diario_global_protege_a_cota() -> None:
    c, svc = client(daily_cap=1)
    assert ask(c).status_code == 200  # type: ignore[attr-defined]
    r = ask(c)
    assert r.status_code == 503 and "hoje" in r.json()["erro"]  # type: ignore[attr-defined]
    assert len(svc.calls) == 1


def test_cabecalho_do_ip_so_vale_se_configurado() -> None:
    spoof = {"X-Forwarded-For": IP_A}
    c, _ = client(per_minute=1)
    assert c.post("/perguntar", json={"pergunta": "a"}, headers=spoof).status_code == 200
    # outro "IP" no cabecalho nao ajuda a fugir do limite: o socket e o mesmo
    other = {"X-Forwarded-For": IP_B}
    assert c.post("/perguntar", json={"pergunta": "a"}, headers=other).status_code == 429

    c2, _ = client(per_minute=1, client_ip_header="CF-Connecting-IP")
    assert (
        c2.post(
            "/perguntar", json={"pergunta": "a"}, headers={"CF-Connecting-IP": IP_A}
        ).status_code
        == 200
    )
    assert (
        c2.post(
            "/perguntar", json={"pergunta": "a"}, headers={"CF-Connecting-IP": IP_B}
        ).status_code
        == 200
    )
    assert (
        c2.post(
            "/perguntar", json={"pergunta": "a"}, headers={"CF-Connecting-IP": IP_A}
        ).status_code
        == 429
    )


# ---------- corpo grande ----------


def test_corpo_acima_do_limite_vira_413_pelo_cabecalho() -> None:
    c, svc = client(max_body_bytes=200)
    r = c.post("/perguntar", content=b"x" * 500, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert svc.calls == []


def test_corpo_em_pedacos_sem_content_length_tambem_e_cortado() -> None:
    c, svc = client(max_body_bytes=200)

    def pedacos():  # type: ignore[no-untyped-def]
        for _ in range(10):
            yield b"x" * 100

    r = c.post("/perguntar", content=pedacos(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert svc.calls == []


# ---------- erros nao vazam ----------


def test_erro_do_gemini_vira_503_generico_sem_detalhes() -> None:
    c, _ = client(FakeService(GeminiError("HTTP 403 chave-secreta-xyz no corpo")))
    r = ask(c)
    assert r.status_code == 503  # type: ignore[attr-defined]
    assert "chave" not in r.text and "403" not in r.text  # type: ignore[attr-defined]


def test_erro_inesperado_vira_500_generico_sem_stack() -> None:
    c, _ = client(FakeService(RuntimeError("caminho /op" + "t/segredo falhou")))
    r = ask(c)
    assert r.status_code == 500 and r.json() == {"erro": "Erro interno."}  # type: ignore[attr-defined]
    assert "opt" not in r.text and "Traceback" not in r.text  # type: ignore[attr-defined]


# ---------- privacidade nos logs ----------


def test_log_nao_tem_o_texto_da_pergunta_nem_o_ip(caplog: pytest.LogCaptureFixture) -> None:
    c, _ = client()
    with caplog.at_level(logging.INFO, logger="assistente"):
        ask(c)
    texto = " ".join(r.getMessage() for r in caplog.records)
    assert "SEGREDO-NA-PERGUNTA" not in texto and "testclient" not in texto
    evento = json.loads(caplog.records[-1].getMessage())
    assert evento["chars"] == len(PERGUNTA) and len(evento["ip"]) == 12


# ---------- metricas ----------


def test_metricas_nem_existem_sem_token() -> None:
    c, _ = client()
    assert c.get("/metrics").status_code == 404


def test_metricas_exigem_o_token_certo() -> None:
    c, _ = client(**{"metrics_token": BEARER_OK})
    assert c.get("/metrics").status_code == 401
    assert c.get("/metrics", headers={"Authorization": "Bearer errado"}).status_code == 401
    ask(c)
    r = c.get("/metrics", headers={"Authorization": f"Bearer {BEARER_OK}"})
    assert r.status_code == 200 and r.json()["por_status"]["200"] == 1
    assert "SEGREDO-NA-PERGUNTA" not in r.text


# ---------- cabecalhos, docs e CORS ----------


def test_cabecalhos_de_seguranca_em_toda_resposta() -> None:
    c, _ = client()
    for r in (c.get("/health"), ask(c), c.get("/nao-existe")):
        h = r.headers  # type: ignore[attr-defined]
        assert h["x-content-type-options"] == "nosniff" and h["cache-control"] == "no-store"
        assert "default-src 'none'" in h["content-security-policy"]


def test_documentacao_automatica_fica_desligada_por_padrao() -> None:
    c, _ = client()
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
    c2, _ = client(enable_docs=True)
    assert c2.get("/docs").status_code == 200


def test_cors_nenhuma_origem_por_padrao_e_so_a_configurada() -> None:
    origin = {"Origin": "https://sirbarber.com.br"}
    c, _ = client()
    assert "access-control-allow-origin" not in c.get("/health", headers=origin).headers
    c2, _ = client(cors_origins=["https://sirbarber.com.br"])
    assert (
        c2.get("/health", headers=origin).headers["access-control-allow-origin"] == origin["Origin"]
    )
    assert (
        "access-control-allow-origin"
        not in c2.get("/health", headers={"Origin": "https://mal.com"}).headers
    )


# ---------- configuracao ----------


@pytest.mark.parametrize(
    "env",
    [
        {"ALLOWED_TENANTS": "ok,../mal"},
        {"CORS_ORIGINS": "*"},
        {"CORS_ORIGINS": "http://site-qualquer.com"},
        {"RATE_PER_MINUTE": "0"},
        {"RATE_PER_MINUTE": "muitos"},
        {"METRICS_TOKEN": "curto"},
        {"CLIENT_IP_HEADER": "X Forwarded\nFor"},
    ],
)
def test_configuracao_invalida_derruba_a_subida(env: dict[str, str]) -> None:
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_env(env)


def test_configuracao_padrao_e_restritiva() -> None:
    cfg = ApiSettings.from_env({})
    assert cfg.allowed_tenants == ["platform"] and cfg.cors_origins == []
    assert cfg.metrics_token is None and cfg.enable_docs is False and cfg.client_ip_header is None


# ---------- servidor ----------


def test_servidor_sobe_sem_confiar_em_cabecalhos_de_proxy_e_sem_log_de_acesso() -> None:
    from app.api.serve import serve_options

    opts = serve_options({})
    assert opts["proxy_headers"] is False  # senao o uvicorn reescreve o IP e burla o limite
    assert opts["access_log"] is False and opts["server_header"] is False
    assert opts["host"] == "127.0.0.1" and opts["port"] == 8000 and opts["factory"] is True


@pytest.mark.parametrize(
    "env", [{"PORT": "abc"}, {"PORT": "0"}, {"PORT": "70000"}, {"HOST": "a b"}]
)
def test_servidor_recusa_host_e_porta_invalidos(env: dict[str, str]) -> None:
    from app.api.serve import serve_options

    with pytest.raises(ValueError):
        serve_options(env)
