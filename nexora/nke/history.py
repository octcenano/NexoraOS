"""NKE History: registro acotado de decisiones, cambios, rollbacks y resultados."""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional


class NKEHistory:
    def __init__(self, size: int = 300):
        self._events: Deque[Dict[str, Any]] = deque(maxlen=size)

    def record(self, kind: str, detail: str, **extra: Any) -> None:
        event = {"time": time.time(), "kind": kind, "detail": detail}
        event.update(extra)
        self._events.append(event)

    def events(self, kind: Optional[str] = None) -> tuple:
        if kind is None:
            return tuple(self._events)
        return tuple(e for e in self._events if e["kind"] == kind)

    def last_rollback(self) -> Optional[Dict[str, Any]]:
        for e in reversed(self._events):
            if e["kind"] == "rollback":
                return e
        return None

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self._events:
            counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        return counts
