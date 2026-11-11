"""Nexora Hub: agentes, modelos IA y herramientas.

Datos reales: agentes del coordinador, backends sondeados en loopback y
aplicaciones instaladas (índice .desktop). Nada simulado sin etiquetarlo.
"""

from __future__ import annotations

import shutil
from typing import Any, Dict, List, Optional

from nexora.core.ai_engine import detect_backends
from nexora.core.registry import SPECIALIST_AGENTS, ModeRegistry

# Categorías de herramientas: mapeo declarativo de categorías XDG.
TOOL_CATEGORIES = ["Development", "Network", "Utility", "System", "Game", "Science"]


class NexoraHub:
    def __init__(self, coordinator=None, index=None, engine=None):
        self.coordinator = coordinator
        self.index = index
        self.engine = engine

    def agents(self, registry: Optional[ModeRegistry] = None) -> Dict[str, Any]:
        """Lista de agentes: modos oficiales + especialistas, con estado real."""
        reg = registry or ModeRegistry()
        known = dict(self.coordinator.agents()) if self.coordinator is not None else {}
        rows = []
        for mode in reg.names():
            running = mode in known
            rows.append({
                "name": mode,
                "kind": "mode",
                "status": "running" if running else "registered",
                "mode_status": reg.mode_status(mode),
                "intensity": reg.intensity(mode),
                "memory_policy": "isolated_per_mode",
            })
        for name, spec in SPECIALIST_AGENTS.items():
            rows.append({
                "name": name,
                "kind": "specialist",
                "status": "running" if name in known else "registered",
                "mode_status": spec.get("status", "basic"),
                "intensity": None,
                "memory_policy": "isolated_per_agent",
            })
        return {"state": "ok", "agents": rows}

    def models(self) -> Dict[str, Any]:
        """Modelos IA por proveedor, sondeando endpoints de loopback reales."""
        backends = detect_backends()
        rows = []
        for backend, info in backends.items():
            rows.append({
                "provider": backend,
                "state": "available" if info["available"] else "unavailable",
                "endpoint": info["endpoint"],
                "models": info["models"],
                "note": "RAM/VRAM estimadas por modelo: no disponible sin metadatos del backend",
            })
        if self.engine is not None:
            current = self.engine.list_models()
            rows.append({
                "provider": self.engine.backend,
                "state": "current",
                "endpoint": self.engine.endpoint,
                "models": current.get("models", []) if current["status"] == "success" else [],
                "selected": self.engine.model,
                "simulated": self.engine.simulated,
            })
        return {"state": "ok", "backends": rows}

    def tools(self) -> Dict[str, Any]:
        """Herramientas instaladas por categoría, desde el índice .desktop real."""
        if self.index is None:
            return {"state": "no_data", "message": "índice de aplicaciones no configurado", "categories": {}}
        apps = self.index.scan()
        categories: Dict[str, List[Dict[str, Any]]] = {c: [] for c in TOOL_CATEGORIES}
        categories["Other"] = []
        for app in apps:
            placed = False
            for cat in app["categories"]:
                if cat in categories:
                    categories[cat].append(app)
                    placed = True
                    break
            if not placed:
                categories["Other"].append(app)
        return {"state": "ok", "categories": categories}
