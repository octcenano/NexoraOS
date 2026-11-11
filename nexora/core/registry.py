"""Registro de modos oficiales y agentes especializados.

Decisiones de producto (PROMPT MAESTRO):
  - Cinco modos oficiales: gaming, hacking, office, stealth y forge. Son
    perfiles combinables, cada uno con niveles de intensidad 1, 2, 3 y full.
  - Creator NO es un modo oficial. Meteorology y Security son agentes
    especializados o funcionalidad transversal, no modos principales.
  - Cada modo declara un estado honesto ('stub' o 'basic') y una ToolPolicy.
  - La intensidad es una declaración de política (LevelPolicy del núcleo
    adaptativo) que consume el reparto de recursos (build_allocation); no
    modifica el sistema por sí misma.
"""

from __future__ import annotations

from typing import Optional

from nexora.agents.base import BaseAgent
from nexora.core.permissions import ToolPolicy

INTENSITY_LEVELS = ("1", "2", "3", "full")
_INTENSITY_TO_LEVEL = {"1": "level1", "2": "level2", "3": "level3", "full": "full"}

MODES = {
    "gaming": {
        "description": "Juego: prioridad de rendimiento para cargas locales",
        "agent": "gaming",
        "status": "stub",
        "tools": ("local_ai", "performance_profile"),
        "default_intensity": "2",
        "effects": {
            "1": "un agente, modelos pequeños, sin ajustes de rendimiento",
            "2": "dos agentes, modelos medianos, prioridad moderada de CPU",
            "3": "cuatro agentes, modelos grandes, prioridad alta de CPU",
            "full": "prioridad total; el ajuste agresivo exige compatibilidad comprobada y aprobación explícita",
        },
    },
    "hacking": {
        "description": "Ciberseguridad autorizada: auditoría defensiva y laboratorios propios",
        "agent": "hacking",
        "status": "stub",
        "tools": ("local_ai", "defensive_audit_readonly", "lab_network_isolated"),
        "default_intensity": "1",
        "effects": {
            "1": "un agente, solo auditoría defensiva de lectura",
            "2": "dos agentes, auditoría y análisis asistido por IA local",
            "3": "cuatro agentes para laboratorios propios aislados",
            "full": "prioridad total del laboratorio; sin capacidades ofensivas autónomas en ningún nivel",
        },
    },
    "office": {
        "description": "Documentos, estudio y productividad diaria",
        "agent": "office",
        "status": "stub",
        "tools": ("local_ai",),
        "default_intensity": "1",
        "effects": {
            "1": "un agente, consumo mínimo",
            "2": "dos agentes, modelos medianos",
            "3": "cuatro agentes, modelos grandes",
            "full": "prioridad total del modo en el reparto de recursos",
        },
    },
    "stealth": {
        "description": "Huella mínima: telemetría desactivada y procesos reducidos",
        "agent": "stealth",
        "status": "stub",
        "tools": ("local_ai",),
        "default_intensity": "1",
        "effects": {
            "1": "un agente, nivel de detalle y consumo mínimos",
            "2": "dos agentes, sin telemetría en ningún caso",
            "3": "cuatro agentes, registro local ampliado",
            "full": "prioridad total; la telemetría permanece desactivada por diseño",
        },
    },
    "forge": {
        "description": "Desarrollo, proyectos, herramientas y modelos locales",
        "agent": "forge",
        "status": "stub",
        "tools": ("local_ai",),
        "default_intensity": "2",
        "effects": {
            "1": "un agente, modelos pequeños",
            "2": "dos agentes, modelos medianos",
            "3": "cuatro agentes, modelos grandes",
            "full": "prioridad total para compilación y modelos locales",
        },
    },
}

# Agentes especializados: no son modos y no aparecen en el selector de perfiles.
SPECIALIST_AGENTS = {
    "meteorology": {
        "description": "Asistente de análisis y previsión meteorológica",
        "status": "basic",
        "tools": ("local_ai", "weather_simulated", "weather_live_opt_in"),
    },
    "security": {
        "description": "Funcionalidad transversal de seguridad defensiva (nexora audit)",
        "status": "basic",
        "tools": ("local_ai", "defensive_audit_readonly"),
    },
}


def intensity_level_policy(level: str):
    """LevelPolicy real del núcleo adaptativo para un nivel de intensidad."""
    if level not in _INTENSITY_TO_LEVEL:
        raise ValueError(f"Nivel de intensidad desconocido: {level}. Opciones: {list(INTENSITY_LEVELS)}")
    from nexora.core.resources import level_policy

    return level_policy(_INTENSITY_TO_LEVEL[level])


class ModeRegistry:
    def __init__(self, modes: Optional[dict] = None):
        self._modes = {k: dict(v) for k, v in (modes or MODES).items()}
        self._intensity = {m: spec.get("default_intensity", "1") for m, spec in self._modes.items()}

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

    # -- intensidad ---------------------------------------------------------
    def intensity(self, mode: str) -> str:
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        return self._intensity[mode]

    def set_intensity(self, mode: str, level: str) -> None:
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        intensity_level_policy(level)  # valida el nivel
        self._intensity[mode] = level

    def intensity_policy(self, mode: str, level: Optional[str] = None) -> dict:
        """Política efectiva de un modo a un nivel de intensidad dado."""
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        lvl = level or self._intensity[mode]
        return {
            "mode": mode,
            "level": lvl,
            "policy": intensity_level_policy(lvl),
            "effect": self._modes[mode]["effects"][lvl],
        }

    def create_agent(self, mode: str, engine=None, **kwargs) -> BaseAgent:
        """Crea el agente de un modo o de un agente especializado registrado."""
        if mode == "meteorology":
            from nexora.agents.meteorology import MeteorologyAgent

            return MeteorologyAgent(engine=engine, **kwargs)
        if mode == "security":
            from nexora.agents.security import SecurityAgent

            return SecurityAgent(engine=engine)
        if not self.is_valid(mode):
            raise ValueError(f"Modo desconocido: {mode}")
        return BaseAgent(name=f"{mode.capitalize()}Agent", mode=mode, engine=engine)
