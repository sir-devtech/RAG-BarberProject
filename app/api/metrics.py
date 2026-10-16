"""Contadores simples da API (sem dados de usuario)."""

from __future__ import annotations

import threading
from collections import Counter, deque
from typing import Any

LATENCY_WINDOW = 500  # guarda so as ultimas medicoes: memoria fixa


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status: Counter[int] = Counter()
        self._reasons: Counter[str] = Counter()
        self._latencies: deque[float] = deque(maxlen=LATENCY_WINDOW)

    def record(self, status: int, latency_ms: float, reason: str | None = None) -> None:
        with self._lock:
            self._status[status] += 1
            if reason:
                self._reasons[reason] += 1
            self._latencies.append(latency_ms)

    @staticmethod
    def _percentile(sorted_values: list[float], fraction: float) -> float:
        if not sorted_values:
            return 0.0
        index = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
        return round(sorted_values[index], 1)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            ordered = sorted(self._latencies)
            return {
                "pedidos": sum(self._status.values()),
                "por_status": {str(k): v for k, v in sorted(self._status.items())},
                "por_motivo": dict(sorted(self._reasons.items())),
                "latencia_ms": {
                    "p50": self._percentile(ordered, 0.50),
                    "p95": self._percentile(ordered, 0.95),
                    "amostras": len(ordered),
                },
            }
