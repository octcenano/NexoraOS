"""Registro de modos. Cada modo tiene su propio agente y memoria privada."""

from __future__ import annotations

from typing import Optional

from nexora.agents.base import BaseAgent

MODES = {
    "forge": {"description": "Desarrollo, proyectos, IA local y productividad", "agent": "forge"},
    "meteorology": {"description": "Asistente de anÃ¡lisis y previsiÃ³n meteorolÃ³gica", "agent": "meteorology"},
    "security": {"description": "Seguridad defensiva y diagnÃ³sticos autorizados", "agent": "security"},
    "creator": {"description": "PlanificaciÃ³n y gestiÃ³n de contenido digital", "agent": "creator"},
    "office": {"description": "Documentos, estudio y productividad diaria", "agent": "office"},
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

    def create_agent(self, mode: str, engine=None, **kwargs) -> BaseAgent:
        """Crea el agente de un modo. Solo meteorologÃ­a tiene lÃ³gica propia;
        el resto son agentes base (stub) con memoria aislada."""
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        if mode == "meteorology":
            from nexora.agents.meteorology import MeteorologyAgent

            return MeteorologyAgent(engine=engine, **kwargs)
        return BaseAgent(name=f"{mode.capitalize()}Agent", mode=mode, engine=engine)
