"""NKE Engine: orquesta monitor -> análisis -> política -> aplicación segura.

Protecciones integradas:
  - Anti-bucle: máximo de acciones por ciclo y cooldown por objetivo, de modo
    que NKE no puede entrar en ciclos de optimización constantes.
  - Detección de degradación: si tras aplicar una acción el hallazgo que la
    motivó empeora, se revierte automáticamente lo aplicado en ese ciclo.
  - Huella propia: se mide la duración de cada ciclo; el intervalo de sondeo
    lo controla el Monitor (aumenta en reposo).
  - Categoría C: registrada como propuesta, nunca ejecutada.
  - API controlada para la interfaz gráfica: las propuestas supervisadas solo
    se aplican mediante approve_proposal(), que valida categoría, objetivo y
    reversibilidad, y registra la decisión en el historial.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from nexora.nke.analyzer import analyze
from nexora.nke.capabilities import detect_capabilities
from nexora.nke.history import NKEHistory
from nexora.nke.monitor import NKMonitor
from nexora.nke.policy import CATEGORY_A, CATEGORY_B, CATEGORY_C, Action, PolicyEngine
from nexora.nke.safety import SafetyController

MAX_ACTIONS_PER_CYCLE = 3
TARGET_COOLDOWN_S = 300.0


class NKEngine:
    def __init__(
        self,
        monitor: Optional[NKMonitor] = None,
        executor: Optional[Any] = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        profile_requests: Optional[List[Dict[str, Any]]] = None,
        primary_mode: Optional[str] = None,
    ):
        self.monitor = monitor or NKMonitor()
        self.clock = clock
        self.sleeper = sleeper
        self.profile_requests = profile_requests or []
        self.primary_mode = primary_mode
        self.caps = self.monitor.capabilities()
        self.policy = PolicyEngine(self.caps)
        self.safety = SafetyController(executor=executor)
        self.history = NKEHistory()
        self._last_applied: Dict[str, float] = {}   # "kind|target" -> timestamp
        self._cycles = 0
        self._active_rollbacks: List[Dict[str, Any]] = []
        self._last_supervised: List[Action] = []

    # -- ciclo ----------------------------------------------------------------
    def run_cycle(self) -> Dict[str, Any]:
        t0 = self.clock()
        self._cycles += 1
        cycle: Dict[str, Any] = {"cycle": self._cycles}

        sample = self.monitor.sample()
        findings = analyze(sample)
        cycle["findings"] = [f["kind"] for f in findings]
        cycle["interval_s"] = sample["interval_s"]

        decisions = self.policy.decide(findings, self.profile_requests, self.primary_mode)
        self._last_supervised = list(decisions[CATEGORY_B])
        cycle["proposals_supervised"] = [
            {"kind": a.kind, "target": a.target, "why": a.justification} for a in decisions[CATEGORY_B]
        ]
        cycle["proposals_protected"] = [
            {"kind": a.kind, "target": a.target, "why": a.justification} for a in decisions[CATEGORY_C]
        ]

        applied, rolled_back = [], []
        now = self.clock()
        for action in decisions[CATEGORY_A]:
            key = action.kind + "|" + action.target
            last = self._last_applied.get(key)
            if last is not None and now - last < TARGET_COOLDOWN_S:
                continue
            if len(applied) >= MAX_ACTIONS_PER_CYCLE:
                break
            try:
                outcome = self.safety.apply(action, user_approved=False)
                self.history.record("apply", f"{action.kind} en {action.target}",
                                    justification=action.justification, rollback=outcome["rollback"])
                self._last_applied[key] = now
                applied.append({"kind": action.kind, "target": action.target})
                self._active_rollbacks.append(outcome["rollback"])
            except Exception as exc:
                self.history.record("error", f"{action.kind} en {action.target}: {type(exc).__name__}: {exc}")
        cycle["applied"] = applied

        # Comprobación post-acción: si la presión no mejora, se revierte lo
        # aplicado en este ciclo (rollback automático de ajustes reversibles).
        if applied:
            post = analyze(self.monitor.sample())
            worse = self._pressure_worse(findings, post)
            if worse:
                for rb in self._active_rollbacks:
                    try:
                        self.safety.rollback(rb)
                        self.history.record("rollback", f"degradación detectada ({worse}); ajuste revertido")
                        rolled_back.append(rb.get("kind", "?"))
                    except Exception as exc:
                        self.history.record("error", f"rollback fallido: {exc}")
                self._active_rollbacks.clear()
        cycle["rolled_back"] = rolled_back

        cycle["duration_ms"] = round((self.clock() - t0) * 1000.0, 2)
        self.history.record("cycle", f"ciclo {self._cycles}", **{
            "findings": cycle["findings"], "applied": len(applied),
            "rolled_back": len(rolled_back), "duration_ms": cycle["duration_ms"],
        })
        return cycle

    @staticmethod
    def _pressure_worse(before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> Optional[str]:
        def max_sev(fs):
            order = {"info": 0, "warning": 1, "critical": 2}
            return max((order.get(f["severity"], 0) for f in fs), default=-1)
        if max_sev(after) > max_sev(before):
            kinds = {f["kind"] for f in after if f["severity"] == "critical"}
            return ", ".join(sorted(kinds)) or "degradación"
        return None

    # -- bucle (para systemd) --------------------------------------------------
    def loop(self, max_cycles: Optional[int] = None) -> None:
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            try:
                self.run_cycle()
            except Exception as exc:
                self.history.record("error", f"error de ciclo: {type(exc).__name__}: {exc}")
            cycles += 1
            self.sleeper(self.monitor.interval)

    # -- API controlada para paneles (Nexora Desktop / CLI) ---------------------
    def last_supervised(self) -> List[Action]:
        """Propuestas supervisadas del último ciclo, pendientes de decisión."""
        return list(self._last_supervised)

    def approve_proposal(self, kind: str, target: str) -> Dict[str, Any]:
        """Aplica una propuesta supervisada con aprobación explícita del usuario.

        Solo acepta acciones de categoría B, reversibles y pendientes del
        último ciclo. Rechaza lo desconocido y lo protegido (categoría C).
        """
        for action in self._last_supervised:
            if action.kind == kind and action.target == target:
                if action.category != CATEGORY_B:
                    raise PermissionError(f"'{kind}' no es una acción supervisada")
                if not action.reversible:
                    raise PermissionError(f"'{kind}' no es reversible: no se aprueba desde la interfaz")
                outcome = self.safety.apply(action, user_approved=True)
                self.history.record("apply", f"{action.kind} en {action.target} (aprobada por el usuario)",
                                    justification=action.justification, rollback=outcome["rollback"])
                self._last_supervised = [a for a in self._last_supervised
                                         if not (a.kind == kind and a.target == target)]
                return outcome
        raise ValueError(f"no hay ninguna propuesta pendiente '{kind}' en '{target}'")

    def reject_proposal(self, kind: str, target: str) -> None:
        """Rechaza una propuesta supervisada pendiente (queda registrada)."""
        for action in self._last_supervised:
            if action.kind == kind and action.target == target:
                self._last_supervised = [a for a in self._last_supervised
                                         if not (a.kind == kind and a.target == target)]
                self.history.record("reject", f"{action.kind} en {action.target}: rechazada por el usuario")
                return
        raise ValueError(f"no hay ninguna propuesta pendiente '{kind}' en '{target}'")

    def undo_last(self) -> Dict[str, Any]:
        """Revierte el último ajuste reversible activo (si lo hay)."""
        if not self._active_rollbacks:
            raise ValueError("no hay ajustes activos que deshacer")
        rb = self._active_rollbacks.pop()
        self.safety.rollback(rb)
        self.history.record("rollback", f"deshacer último ajuste ({rb.get('kind', '?')})")
        return {"state": "ok", "rolled_back": rb}

    # -- estado -----------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "capabilities": self.caps,
            "cycles": self._cycles,
            "monitor_interval_s": self.monitor.interval,
            "history_summary": self.history.summary(),
            "supervised_pending": [e for e in self.history.events("apply")][-5:],
            "last_rollback": self.history.last_rollback(),
        }
