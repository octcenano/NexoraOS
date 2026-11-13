"""Modelo puro del panel del Nexora Kernel Engine para la vista GTK.

Separación modelo/vista: este módulo no importa GTK y se prueba sin sesión
gráfica. La vista (gtkui) agenda las instantáneas periódicas del productor
con AsyncRunner (hilo de trabajo) y las consume en el hilo gráfico mediante
el mecanismo de entrega inyectado (GLib.idle_add en producción).

Las acciones que cambian el estado del sistema (aprobar, rechazar, deshacer)
exigen confirmación explícita (confirmed=True): sin ella devuelven el estado
"confirmation_required" y no tienen ningún efecto.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Callable, Dict, List, Optional

from nexora.desktop.nke_control import NKEControl

CATEGORY_LABELS = {
    "automatic": "automática",
    "supervised": "supervisada",
    "protected": "protegida",
}

CONFIRMATION_REQUIRED = "confirmation_required"


def _confirmation(kind: str, target: str) -> Dict[str, Any]:
    return {
        "state": CONFIRMATION_REQUIRED,
        "kind": kind,
        "target": target,
        "message": "requiere confirmación explícita del usuario; sin ella no se aplica ningún cambio",
    }


class NkePanelModel:
    """Instantáneas y acciones del panel NKE sobre NKEControl."""

    def __init__(self, control: NKEControl):
        self.control = control

    def snapshot(self) -> Dict[str, Any]:
        ov = self.control.overview()
        pending: List[Dict[str, Any]] = []
        for p in ov.get("pending_supervised", []):
            explain = self.control.explain(p["kind"])
            pending.append({
                "kind": p["kind"],
                "target": p["target"],
                "category": p.get("category"),
                "category_label": CATEGORY_LABELS.get(p.get("category"), str(p.get("category"))),
                "reversible": p.get("reversible"),
                "impact": p.get("why", ""),
                "description": explain.get("description", ""),
                "implemented": explain.get("state") != "unavailable",
                "explain_state": explain.get("state", "error"),
                "explain_message": explain.get("message"),
            })
        return {
            "state": "ok",
            "kernel_release": ov.get("kernel_release"),
            "cycles": ov.get("cycles"),
            "pending": pending,
            "policies": ov.get("policies", {}),
            "modifications": ov.get("modifications"),
            "last_rollback": ov.get("last_rollback"),
            "footprint": ov.get("footprint"),
        }

    def explain(self, kind: str) -> Dict[str, Any]:
        return self.control.explain(kind)

    def run_cycle(self) -> Dict[str, Any]:
        """Operación lenta: el llamante debe ejecutarla fuera del hilo gráfico."""
        return self.control.refresh()

    def approve(self, kind: str, target: str, confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            return _confirmation(kind, target)
        return self.control.approve(kind, target)

    def reject(self, kind: str, target: str, confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            return _confirmation(kind, target)
        return self.control.reject(kind, target)

    def undo_last(self, confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            return _confirmation("undo_last", "último ajuste")
        return self.control.undo_last()

    def history(self) -> Dict[str, Any]:
        return self.control.history()


class Poller:
    """Instantáneas periódicas del panel.

    La vista agenda poller.producer en un hilo de trabajo y entrega el
    resultado a consume() en el hilo gráfico; consume notifica a los
    suscriptores y registra los fallos de suscriptores defectuosos sin
    detener el refresco. tick() produce y consume en el mismo hilo: útil en
    pruebas y en la primera carga.
    """

    def __init__(self, producer: Callable[[], Dict[str, Any]], interval_ms: int = 2000):
        self.producer = producer
        self.interval_ms = interval_ms
        self.last: Optional[Dict[str, Any]] = None
        self.ticks = 0
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self.errors: deque = deque(maxlen=50)

    def consume(self, snapshot: Dict[str, Any]) -> bool:
        self.ticks += 1
        self.last = snapshot
        for cb in list(self.listeners):
            try:
                cb(self.last)
            except Exception as exc:
                self.errors.append({
                    "listener": getattr(cb, "__name__", "listener"),
                    "error": str(exc),
                })
        return True  # compatible con GLib.timeout_add

    def tick(self) -> bool:
        try:
            snap = self.producer()
        except Exception as exc:
            snap = {"state": "error", "message": str(exc)}
        return self.consume(snap)


class AsyncRunner:
    """Ejecuta operaciones lentas fuera del hilo gráfico.

    deliver inyecta el mecanismo de retorno: en GTK, GLib.idle_add para que
    la devolución se ejecute en el hilo gráfico; en pruebas, una llamada
    directa. Las excepciones del hilo de trabajo se entregan por on_error;
    nunca se propagan de forma silenciosa.
    """

    def __init__(self, deliver: Callable[[Callable[[], None]], None]):
        self.deliver = deliver
        self._lock = threading.Lock()
        self.pending = 0

    def submit(self, fn: Callable[[], Any], on_done: Callable[[Any], None],
               on_error: Optional[Callable[[Exception], None]] = None):
        with self._lock:
            self.pending += 1

        def finish(cb: Optional[Callable], *args) -> None:
            with self._lock:
                self.pending -= 1
            if cb is not None:
                self.deliver(lambda: cb(*args))

        def worker() -> None:
            try:
                result = fn()
            except Exception as exc:
                finish(on_error, exc)
            else:
                finish(on_done, result)

        thread = threading.Thread(target=worker, daemon=True, name="nexora-desktop-worker")
        thread.start()
        return thread
