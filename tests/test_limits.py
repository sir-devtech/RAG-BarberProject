import pytest

from app.api.limits import MAX_TRACKED_IPS, DailyCap, SlidingWindowLimiter
from app.api.lru import LruQueryEmbedder
from app.api.metrics import Metrics


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_bloqueia_apos_o_limite_e_informa_quanto_esperar() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(2, 60, clock)
    assert limiter.allow("ip")[0] and limiter.allow("ip")[0]
    allowed, wait = limiter.allow("ip")
    assert not allowed and 1 <= wait <= 61


def test_libera_de_novo_quando_a_janela_passa() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, clock)
    assert limiter.allow("ip")[0]
    assert not limiter.allow("ip")[0]
    clock.now += 61
    assert limiter.allow("ip")[0]


def test_cada_ip_tem_o_proprio_limite() -> None:
    limiter = SlidingWindowLimiter(1, 60, Clock())
    assert limiter.allow("a")[0] and limiter.allow("b")[0]
    assert not limiter.allow("a")[0]


def test_pedido_bloqueado_nao_renova_a_janela() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, clock)
    limiter.allow("ip")
    for _ in range(5):
        clock.now += 10
        assert not limiter.allow("ip")[0]  # tentar de novo nao pode adiar o desbloqueio
    clock.now += 11  # 61s desde o unico pedido aceito
    assert limiter.allow("ip")[0]


def test_memoria_nunca_passa_do_teto_mesmo_com_ips_inventados() -> None:
    limiter = SlidingWindowLimiter(1, 3600, Clock())
    for i in range(MAX_TRACKED_IPS + 500):
        limiter.allow(f"ip-{i}")
    assert limiter.tracked() <= MAX_TRACKED_IPS


def test_limites_invalidos_sao_recusados() -> None:
    with pytest.raises(ValueError):
        SlidingWindowLimiter(0, 60)
    with pytest.raises(ValueError):
        DailyCap(0)


def test_teto_diario_zera_quando_o_dia_muda() -> None:
    day = ["2026-10-16"]
    cap = DailyCap(2, today=lambda: day[0])
    assert cap.take() and cap.take() and not cap.take()
    day[0] = "2026-10-17"
    assert cap.take()
    assert cap.used == 1


class FakeEmbedder:
    model, dimensions = "m", 2

    def __init__(self) -> None:
        self.calls = 0

    def embed_documents(self, texts: object) -> object:
        raise AssertionError

    def embed_query(self, text: str) -> object:
        self.calls += 1
        return [[float(len(text)), 0.0]]


def test_lru_reaproveita_e_nunca_passa_do_teto() -> None:
    inner = FakeEmbedder()
    lru = LruQueryEmbedder(inner, maxsize=3)  # type: ignore[arg-type]
    lru.embed_query("a")
    lru.embed_query("a")
    assert inner.calls == 1
    for text in ["b", "cc", "ddd", "eeee", "fffff"]:
        lru.embed_query(text)
    assert len(lru) == 3
    lru.embed_query("a")  # ja foi descartada: precisa chamar de novo
    assert inner.calls == 7


def test_metricas_contam_status_motivos_e_percentis() -> None:
    metrics = Metrics()
    for ms in (10, 20, 30, 40, 1000):
        metrics.record(200, ms, "ok")
    metrics.record(429, 0, "limite_por_minuto")
    snap = metrics.snapshot()
    assert snap["pedidos"] == 6
    assert snap["por_status"] == {"200": 5, "429": 1}
    assert snap["por_motivo"]["ok"] == 5
    assert snap["latencia_ms"]["p95"] >= snap["latencia_ms"]["p50"]
