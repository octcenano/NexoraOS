"""Registro de modos. Cada modo tiene su propio agente, memoria privada y política de herramientas."""

from __future__ import annotations

from typing import Optional

from nexora.agents.base import BaseAgent
from nexora.core.permissions import ToolPolicy

MODES = {
    "forge": {
        "description": "Desarrollo, proyectos, IA local y productividad",
        "agent": "forge",
        "status": "stub",
        "tools": ("local_ai",),
    },
    "meteorology": {
        "description": "Asistente de análisis y previsión meteorológica",
        "agent": "meteorology",
        "status": "basic",
        "tools": ("local_ai", "weather_simulated", "weather_live_opt_in"),
    },
    "security": {
        "description": "Seguridad defensiva y diagnósticos autorizados",
        "agent": "security",
        "status": "basic",
        "tools": ("local_ai", "defensive_audit_readonly"),
    },
    "creator": {
        "description": "Planificación y gestión de contenido digital",
        "agent": "creator",
        "status": "stub",
        "tools": ("local_ai",),
    },
    "office": {
        "description": "Documentos, estudio y productividad diaria",
        "agent": "office",
        "status": "stub",
        "tools": ("local_ai",),
    },
}


class ModeRegistry:
    def __init__(self, modes: Optional[dict] = None):
        self._modes = {k: dict(v) for k, v in (modes or MODES).items()}

    def get_modes(self) -> dict:
        return {k: dict(v) for k, v in self._modes.items()}

    def names(self) -> tuple:
        return tuple(self._modes)

    def is_valid(self, mode: str) -> bool:
        return mode in self._modes

    def mode_status(self, mode: str) -> str:
        """Estado honesto del modo: 'stub' (solo registrado), 'basic' o superior."""
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        return self._modes[mode].get("status", "stub")

    def tool_policy(self, mode: str) -> ToolPolicy:
        """Política de herramientas del modo. 'network_remote' exige aprobación siempre."""
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        tools = tuple(self._modes[mode].get("tools", ()))
        return ToolPolicy(mode=mode, allowed_tools=tools)

    def create_agent(self, mode: str, engine=None, **kwargs) -> BaseAgent:
        """Crea el agente de un modo. Los modos 'stub' son agentes base con memoria aislada."""
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        if mode == "meteorology":
            from nexora.agents.meteorology import MeteorologyAgent

            return MeteorologyAgent(engine=engine, **kwargs)
        if mode == "security":
            from nexora.agents.security import SecurityAgent

            return SecurityAgent(engine=engine)
        return BaseAgent(name=f"{mode.capitalize()}Agent", mode=mode, engine=engine)
