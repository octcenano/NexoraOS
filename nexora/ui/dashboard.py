"""Runtime de la interfaz: modelo de estado + vista de terminal.

Es el modelo que una GUI gráfica consumirá (``render_layout``); hoy la única
vista implementada es de texto (``render_text``). No hay ventana gráfica aún.

Estilo: identidad discreta y profesional (marco fino, estados con símbolos
neutros). Sin colores ni estética de terminal clásica.
"""

from __future__ import annotations

from typing import Optional

from nexora import __version__
from nexora.agents.base import BaseAgent
from nexora.connectors.account_hub import AccountHub
from nexora.core.registry import ModeRegistry


class NexoraDashboard:
    def __init__(self, core_registry: Optional[ModeRegistry] = None, hub: Optional[AccountHub] = None,
                 engine=None, initial_mode: str = "forge"):
        self.registry = core_registry or ModeRegistry()
        self.hub = hub or AccountHub()
        self.engine = engine
        self.status = "READY"
        self._agents: dict = {}
        if not self.registry.is_valid(initial_mode):
            raise ValueError(f"Modo desconocido: {initial_mode}")
        self.active_mode = initial_mode
        self._agent_for(initial_mode)

    def _agent_for(self, mode: str) -> BaseAgent:
        # Un agente por modo, reutilizado: su memoria privada sobrevive al cambio de modo.
        if mode not in self._agents:
            self._agents[mode] = self.registry.create_agent(mode, engine=self.engine)
        return self._agents[mode]

    @property
    def active_agent(self) -> BaseAgent:
        return self._agent_for(self.active_mode)

    def kernel_engine_summary(self) -> Optional[dict]:
        """Panel Kernel Engine: capacidades reales del kernel (solo lectura).

        Si NKE no puede leer las interfaces (kernel sin PSI, contenedor sin
        /sys), devuelve None y el dashboard lo muestra como no disponible.
        """
        try:
            from nexora.nke.kernel_extension import ExtensionAPI
            res = ExtensionAPI().request("dashboard", "kernel_status")
            return res["data"] if res["status"] == "ok" else None
        except Exception:
            return None

    @property
    def widgets(self) -> dict:
        return {
            "mode_selector": list(self.registry.names()),
            "active_intensity": self.registry.intensity(self.active_mode),
            "account_hub_status": self.hub.summary(),
            "active_agent": self.active_agent.name,
            "mode_status": self.registry.mode_status(self.active_mode),
            "ai_engine": (
                {"backend": self.engine.backend, "simulated": self.engine.simulated} if self.engine else None
            ),
            "kernel_engine": self.kernel_engine_summary(),
        }

    def switch_mode(self, mode_name: str) -> bool:
        if not self.registry.is_valid(mode_name):
            return False
        self.active_mode = mode_name
        self._agent_for(mode_name)
        return True

    def set_intensity(self, level: str) -> None:
        """Fija la intensidad del modo activo (validada contra los niveles reales)."""
        self.registry.set_intensity(self.active_mode, level)

    def ask(self, prompt: str) -> str:
        return self.active_agent.process_prompt(prompt)

    def render_layout(self) -> dict:
        return {
            "header": f"NEXORA OS - Dashboard v{__version__}",
            "active_mode": self.active_mode,
            "widgets": self.widgets,
            "system_status": self.status,
        }

    def render_text(self) -> str:
        layout = self.render_layout()
        w = layout["widgets"]
        modes = " ".join(f"[{m}]" if m == self.active_mode else f" {m} " for m in w["mode_selector"])
        if w["ai_engine"]:
            engine = w["ai_engine"]["backend"] + (" (simulado)" if w["ai_engine"]["simulated"] else "")
        else:
            engine = "no configurado"
        ke = w.get("kernel_engine")
        if ke:
            kernel_line = (f"kernel {ke['release']} · PSI {'sí' if ke['psi'] else 'no'} · "
                           f"cgroups v2 {'sí' if ke['cgroup_v2'] else 'no'}")
        else:
            kernel_line = "no disponible"
        status_label = {"stub": "solo registrado (stub)", "basic": "funcionalidad básica"}.get(
            w.get("mode_status", "stub"), w.get("mode_status", ""))
        lines = [
            "┌─────────────────────────────────────────────",
            f"│ {layout['header']}",
            "├─────────────────────────────────────────────",
            f"│ Estado       : {layout['system_status']}",
            f"│ Modo activo  : {layout['active_mode']} ({w['active_agent']}) · {status_label}",
            f"│ Intensidad   : {w['active_intensity']}",
            f"│ Modos        : {modes}",
            f"│ Account Hub  : {w['account_hub_status']}",
            f"│ Motor IA     : {engine}",
            f"│ Kernel Engine: {kernel_line}",
            "└─────────────────────────────────────────────",
        ]
        return "\n".join(lines)
