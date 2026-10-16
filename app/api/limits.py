"""Limites de uso: por IP (janela deslizante) e teto diario global. Tudo em memoria.

Em memoria significa que reiniciar o servico zera os contadores. Para uma demo isso e aceitavel
e evita depender de banco; para varias instancias seria preciso um armazenamento compartilhado.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], float]
MAX_TRACKED_IPS = 10_000  # teto de memoria: ninguem consegue encher a tabela com IPs inventados


class SlidingWindowLimiter:
    """No maximo `limit` pedidos por `window` segundos para cada chave (ex.: IP)."""

    def __init__(self, limit: int, window: float, clock: Clock = time.monotonic) -> None:
        if limit < 1 or window <= 0:
            raise ValueError("limit >= 1 e window > 0")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """(permitido, segundos ate poder tentar de novo). Registra o pedido se permitido."""
        now = self._clock()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = self._hits[key] = deque()
                self._evict_if_needed(now, keep=key)
            cutoff = now - self._window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            self._hits.move_to_end(key)
            if len(hits) >= self._limit:
                return False, max(1, int(hits[0] + self._window - now) + 1)
            hits.append(now)
            return True, 0

    def _evict_if_needed(self, now: float, keep: str) -> None:
        """Mantem a tabela no teto. NUNCA remove `keep`: e a chave que acabou de ser criada."""
        if len(self._hits) <= MAX_TRACKED_IPS:
            return
        cutoff = now - self._window
        stale = [k for k, h in self._hits.items() if k != keep and (not h or h[-1] <= cutoff)]
        for key in stale:
            del self._hits[key]
        while len(self._hits) > MAX_TRACKED_IPS:
            oldest = next(iter(self._hits))
            if oldest == keep:
                self._hits.move_to_end(keep)
                continue
            del self._hits[oldest]  # descarta o menos recente

    def tracked(self) -> int:
        return len(self._hits)


def _utc_day() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class DailyCap:
    """Teto de pedidos por dia (UTC), para proteger a cota gratuita do Gemini."""

    def __init__(self, cap: int, today: Callable[[], str] = _utc_day) -> None:
        if cap < 1:
            raise ValueError("cap >= 1")
        self._cap = cap
        self._today = today
        self._day = today()
        self._used = 0
        self._lock = threading.Lock()

    def take(self) -> bool:
        with self._lock:
            day = self._today()
            if day != self._day:
                self._day, self._used = day, 0
            if self._used >= self._cap:
                return False
            self._used += 1
            return True

    @property
    def used(self) -> int:
        return self._used
