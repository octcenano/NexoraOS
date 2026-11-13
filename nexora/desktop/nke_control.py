"""Nexora NKE Control: panel del Nexora Kernel Engine.

Toda operación pasa por la API controlada del motor (NKEngine). El panel
nunca ejecuta operaciones privilegiadas: las acciones de categoría C solo se
muestran como propuestas documentadas, y las de categoría B requieren
aprobación explícita del usuario, que se registra en el historial.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from nexora.nke.engine import NKEngine
from nexora.nke.policy import ACTION_CATALOG


class NKEControl:
    def __init__(self, engine: Optional[NKEngine] = None):
        self.engine = engine or NKEngine()

    def overview(self) -> Dict[str, Any]:
        st = self.engine.status()
        caps = st["capabilities"]
        # Huella propia del NKE: duración de los ciclos registrados.
        durations = [e.get("duration_ms") for e in self.engine.history.events("cycle")
                     if isinstance(e.get("duration_ms"), (int, float))]
        footprint = {
            "cycles_measured": len(durations),
            "avg_cycle_ms": round(sum(durations) / len(durations), 2) if durations else None,
            "max_cycle_ms": max(durations) if durations else None,
            "monitor_interval_s": st["monitor_interval_s"],
        }
        return {
            "state": "ok",
            "kernel_release": caps.get("kernel_release"),
            "capabilities": caps,
            "ebpf": {
                "available": bool(caps.get("can_ebpf")),
                "note": "sin programa eBPF cargado: degradación segura a monitorización en espacio de usuario",
            },
            "cycles": st["cycles"],
            "policies": {kind: {"category": spec["category"], "implemented": spec.get("implemented", True)}
                         for kind, spec in ACTION_CATALOG.items()},
            "pending_supervised": self.pending(),
            "history_summary": st["history_summary"],
            "last_rollback": st["last_rollback"],
            "modifications": st.get("modifications"),
            "footprint": footprint,
        }

    def refresh(self) -> Dict[str, Any]:
        """Ejecuta un ciclo de diagnóstico/optimización controlado."""
        cycle = self.engine.run_cycle()
        return {"state": "ok", "cycle": cycle}

    def pending(self) -> List[Dict[str, Any]]:
        """Acciones supervisadas (categoría B) pendientes de decisión."""
        return [{"kind": a.kind, "target": a.target, "category": a.category,
                 "reversible": a.reversible, "why": a.justification}
                for a in self.engine.last_supervised()]

    def explain(self, kind: str) -> Dict[str, Any]:
        """Explicación de una política: categoría, reversibilidad, implementación."""
        spec = ACTION_CATALOG.get(kind)
        if spec is None:
            return {"state": "error", "message": "acción desconocida: " + str(kind)}
        out = {"state": "ok", "kind": kind, "category": spec["category"],
               "reversible": spec["reversible"], "description": spec["description"]}
        if not spec.get("implemented", True):
            out["state"] = "unavailable"
            out["message"] = "acción declarada en el catálogo pero sin implementación segura"
        return out

    def approve(self, kind: str, target: str) -> Dict[str, Any]:
        """Aprueba una acción supervisada pendiente. Rechaza lo desconocido o protegido."""
        try:
            result = self.engine.approve_proposal(kind, target)
        except (ValueError, PermissionError) as exc:
            return {"state": "rejected", "message": str(exc)}
        return {"state": "ok", "applied": result}

    def reject(self, kind: str, target: str) -> Dict[str, Any]:
        try:
            self.engine.reject_proposal(kind, target)
        except ValueError as exc:
            return {"state": "error", "message": str(exc)}
        return {"state": "ok", "message": "propuesta rechazada y registrada"}

    def undo_last(self) -> Dict[str, Any]:
        try:
            return self.engine.undo_last()
        except ValueError as exc:
            return {"state": "no_data", "message": str(exc)}
        except OSError as exc:
            return {"state": "error", "message": str(exc)}

    def modifications(self) -> List[Dict[str, Any]]:
        """Estado de cada modificación: id, ciclo, acción y estado."""
        return self.engine.modifications()

    def history(self) -> Dict[str, Any]:
        return {"state": "ok", "events": list(self.engine.history.events())}
