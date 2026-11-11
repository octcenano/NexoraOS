"""NexoraDesktopApp: orquestador de los módulos de Nexora Desktop.

Ciclo de vida explícito (start/shutdown), registro de eventos acotado y
arranque de la vista GTK diferido. Nunca se ejecuta como root.
"""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Any, Deque, Dict, Optional

from nexora.desktop.dashboard import DashboardModel
from nexora.desktop.hub import NexoraHub
from nexora.desktop.mode_center import ModeCenter
from nexora.desktop.nke_control import NKEControl
from nexora.desktop.shell import PANEL_LAYOUT, QUICK_ACCESS, ApplicationIndex, GlobalSearch
from nexora.desktop.system_center import SystemCenter


class DesktopUnavailableError(RuntimeError):
    """La vista gráfica no puede iniciarse (PyGObject/GTK3 ausente o sin DISPLAY)."""


class NexoraDesktopApp:
    MODULES = ("dashboard", "mode_center", "nke_control", "hub", "system_center")

    def __init__(self, engine=None, coordinator=None, nke=None, clock=time.monotonic):
        if os.getuid() == 0:
            raise PermissionError("Nexora Desktop no debe ejecutarse como root")
        self.clock = clock
        self.engine = engine
        self.coordinator = coordinator
        self.nke = nke
        self.registry = None
        self.mode_center: Optional[ModeCenter] = None
        self.nke_control: Optional[NKEControl] = None
        self.hub: Optional[NexoraHub] = None
        self.system_center: Optional[SystemCenter] = None
        self.dashboard: Optional[DashboardModel] = None
        self.search: Optional[GlobalSearch] = None
        self._events: Deque[Dict[str, Any]] = deque(maxlen=100)
        self._running = False

    # -- ciclo de vida -------------------------------------------------------
    def start(self) -> None:
        from nexora.core.registry import ModeRegistry

        self.registry = ModeRegistry()
        self.mode_center = ModeCenter(registry=self.registry)
        self.nke_control = NKEControl(engine=self.nke)
        self.hub = NexoraHub(coordinator=self.coordinator, index=ApplicationIndex(), engine=self.engine)
        self.system_center = SystemCenter()
        self.dashboard = DashboardModel(engine=self.engine, nke=self.nke, coordinator=self.coordinator)
        self.search = GlobalSearch()
        self._running = True
        self._log("start", "Nexora Desktop iniciado")

    def shutdown(self) -> None:
        self._running = False
        self._log("shutdown", "cierre limpio de Nexora Desktop")

    @property
    def running(self) -> bool:
        return self._running

    def _log(self, kind: str, detail: str) -> None:
        self._events.append({"time": self.clock(), "kind": kind, "detail": detail})

    def events(self) -> tuple:
        return tuple(self._events)

    # -- modelo completo para la vista ---------------------------------------
    def layout(self) -> Dict[str, Any]:
        if not self._running:
            raise RuntimeError("Nexora Desktop no está iniciado; llama a start() primero")
        return {
            "panel": PANEL_LAYOUT,
            "quick_access": QUICK_ACCESS,
            "dashboard": self.dashboard.snapshot(),
            "mode_center": self.mode_center.overview(),
            "nke_control": self.nke_control.overview(),
            "hub": {"agents": self.hub.agents(self.registry), "tools": self.hub.tools()},
            "system_center": self.system_center.sections(),
        }

    # -- vista GTK -----------------------------------------------------------
    def run_gtk(self) -> int:
        """Arranca la vista GTK3. Importación diferida y error claro si falta."""
        if not self._running:
            self.start()
        try:
            import gi  # noqa: F401
        except ImportError:
            raise DesktopUnavailableError(
                "PyGObject (python-gobject) no está instalado: instálalo o usa 'nexora desktop --json'"
            )
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise DesktopUnavailableError("no hay sesión gráfica activa (DISPLAY/WAYLAND_DISPLAY vacíos)")
        from nexora.desktop.gtkui import run as run_gtkui

        return run_gtkui(self)
