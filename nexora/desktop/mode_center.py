"""Nexora Mode Center: gestión de los cinco modos oficiales.

Coordina con el núcleo adaptativo (build_allocation) y guarda una instantánea
reversible de la configuración activa. Los cambios previstos son un plan
declarativo: no tocan el sistema hasta que una capa autorizada lo aplique.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from nexora.core.registry import INTENSITY_LEVELS, ModeRegistry
from nexora.core.resources import build_allocation

# Conflictos declarativos entre modos: pares incompatibles y por qué.
CONFLICTS: Dict[frozenset, str] = {
    frozenset({"stealth", "gaming"}):
        "Stealth exige huella mínima; Gaming prioriza rendimiento: el primario debe declararse explícitamente",
    frozenset({"stealth", "forge"}):
        "Forge usa modelos grandes; Stealth limita procesos y consumo",
}


class ModeCenter:
    def __init__(self, registry: Optional[ModeRegistry] = None, inventory_fn=None):
        self.registry = registry or ModeRegistry()
        self._inventory_fn = inventory_fn
        self.active_modes: List[str] = ["forge"]
        self._previous: Optional[Dict[str, Any]] = None

    # -- helpers -------------------------------------------------------------
    def _inventory(self):
        return self._inventory_fn() if self._inventory_fn else None

    def _level_for(self, mode: str) -> str:
        return {"1": "level1", "2": "level2", "3": "level3", "full": "full"}[self.registry.intensity(mode)]

    # -- operaciones ---------------------------------------------------------
    def activate(self, mode: str, intensity: Optional[str] = None) -> Dict[str, Any]:
        if not self.registry.is_valid(mode):
            return {"state": "error", "message": "modo desconocido: " + str(mode)}
        self._snapshot()
        self.active_modes = [mode]
        if intensity:
            self.registry.set_intensity(mode, intensity)
        return {"state": "ok", "active_modes": list(self.active_modes),
                "intensity": self.registry.intensity(mode)}

    def combine(self, modes: List[str]) -> Dict[str, Any]:
        if not modes:
            return {"state": "error", "message": "se necesita al menos un modo"}
        for m in modes:
            if not self.registry.is_valid(m):
                return {"state": "error", "message": "modo desconocido: " + str(m)}
        if len(set(modes)) != len(modes):
            return {"state": "error", "message": "modos duplicados en la combinación"}
        self._snapshot()
        self.active_modes = list(modes)
        return {"state": "ok", "active_modes": list(self.active_modes),
                "primary": self.active_modes[0]}

    def set_intensity(self, mode: str, level: str) -> Dict[str, Any]:
        if level not in INTENSITY_LEVELS:
            return {"state": "error",
                    "message": "nivel inválido: " + str(level) + ". Opciones: " + str(list(INTENSITY_LEVELS))}
        if not self.registry.is_valid(mode):
            return {"state": "error", "message": "modo desconocido: " + str(mode)}
        self.registry.set_intensity(mode, level)
        return {"state": "ok", "mode": mode, "intensity": level}

    def deactivate(self, mode: str) -> Dict[str, Any]:
        if mode not in self.active_modes:
            return {"state": "error", "message": "el modo '" + str(mode) + "' no está activo"}
        if len(self.active_modes) == 1:
            return {"state": "error", "message": "no se puede desactivar el único modo activo"}
        self.active_modes = [m for m in self.active_modes if m != mode]
        return {"state": "ok", "active_modes": list(self.active_modes)}

    # -- información ---------------------------------------------------------
    def planned_changes(self) -> Dict[str, Any]:
        """Plan previsto (reparto de recursos) para la configuración activa."""
        level = self._level_for(self.active_modes[0])
        try:
            plan = build_allocation(self.active_modes, level=level, inv=self._inventory())
        except ValueError as exc:
            return {"state": "error", "message": str(exc)}
        return {
            "state": "ok",
            "level": plan.level,
            "primary": plan.primary_mode,
            "shares": [s.__dict__ for s in plan.shares],
            "warnings": list(plan.warnings),
            "requires_approval": plan.requires_approval,
            "note": "plan declarativo: no modifica el sistema hasta que una capa autorizada lo aplique",
        }

    def conflicts(self) -> List[Dict[str, str]]:
        active = set(self.active_modes)
        out = []
        for pair, why in CONFLICTS.items():
            if pair <= active:
                out.append({"modes": sorted(pair), "reason": why})
        return out

    def overview(self) -> Dict[str, Any]:
        return {
            "active_modes": list(self.active_modes),
            "intensities": {m: self.registry.intensity(m) for m in self.active_modes},
            "statuses": {m: self.registry.mode_status(m) for m in self.active_modes},
            "conflicts": self.conflicts(),
            "previous_available": self._previous is not None,
        }

    # -- reversibilidad ------------------------------------------------------
    def _snapshot(self) -> None:
        self._previous = {
            "active_modes": list(self.active_modes),
            "intensities": {m: self.registry.intensity(m) for m in self.active_modes},
        }

    def restore_previous(self) -> Dict[str, Any]:
        if self._previous is None:
            return {"state": "no_data", "message": "no hay configuración anterior que recuperar"}
        prev = self._previous
        self._previous = None
        self.active_modes = list(prev["active_modes"])
        for mode, level in prev["intensities"].items():
            self.registry.set_intensity(mode, level)
        return {"state": "ok", "restored": prev}
