"""Nexora System Center: configuración del sistema.

Reutiliza las herramientas de XFCE y Linux (principio de no duplicación).
Cada sección declara entradas con comandos fijos y validados: la interfaz
nunca ejecuta comandos arbitrarios. Los estados son explícitos.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, List, Optional

SECTIONS: Dict[str, Dict[str, Any]] = {
    "hardware": {"label": "Hardware", "entries": [
        {"label": "Información del sistema", "command": "xfce4-settings-manager"},
    ]},
    "displays": {"label": "Pantallas", "entries": [
        {"label": "Configuración de pantallas", "command": "xfce4-display-settings"},
    ]},
    "audio": {"label": "Audio", "entries": [
        {"label": "Mezclador PulseAudio/PipeWire", "command": "pavucontrol"},
    ]},
    "input": {"label": "Teclado y ratón", "entries": [
        {"label": "Teclado", "command": "xfce4-keyboard-settings"},
        {"label": "Ratón", "command": "xfce4-mouse-settings"},
    ]},
    "locale": {"label": "Idioma y región", "entries": [
        {"label": "Configuración regional", "command": "xfce4-settings-manager"},
    ]},
    "network": {"label": "Red", "entries": [
        {"label": "Conexiones de red", "command": "nm-connection-editor"},
    ]},
    "users": {"label": "Usuarios", "entries": [
        {"label": "Gestión de usuarios (xfce4-settings no la cubre)", "command": None,
         "note": "pendiente de implementación propia; no se muestra un botón falso"},
    ]},
    "storage": {"label": "Almacenamiento", "entries": [
        {"label": "Gestor de archivos", "command": "thunar"},
    ]},
    "updates": {"label": "Actualizaciones", "entries": [
        {"label": "Actualización de paquetes (pacman)", "command": None,
         "note": "requiere privilegios: pendiente de integración con polkit; no se ejecuta desde la interfaz"},
    ]},
    "services": {"label": "Servicios", "entries": [
        {"label": "Estado de servicios Nexora", "command": None,
         "note": "consultable en el Dashboard; la gestión requiere privilegios y está pendiente"},
    ]},
    "privacy": {"label": "Privacidad", "entries": [
        {"label": "Telemetría: desactivada por diseño", "command": None,
         "note": " Nexora no envía telemetría; no hay nada que configurar"},
    ]},
    "security": {"label": "Seguridad", "entries": [
        {"label": "Auditoría defensiva", "command": None,
         "note": "integrada en nexora audit y en el Hub"},
    ]},
    "power": {"label": "Energía", "entries": [
        {"label": "Gestión de energía", "command": "xfce4-power-manager-settings"},
    ]},
    "appearance": {"label": "Apariencia", "entries": [
        {"label": "Apariencia", "command": "xfce4-appearance-settings"},
        {"label": "Gestor de ventanas", "command": "xfwm4-settings"},
    ]},
}


class SystemCenter:
    """Secciones y lanzamiento validado de herramientas externas."""

    def __init__(self, allow_launch: bool = True):
        self.allow_launch = allow_launch

    def sections(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, spec in SECTIONS.items():
            entries = []
            for entry in spec["entries"]:
                cmd = entry.get("command")
                if cmd is None:
                    entries.append({"label": entry["label"], "state": "not_implemented",
                                    "note": entry.get("note", "")})
                else:
                    available = shutil.which(cmd) is not None
                    entries.append({
                        "label": entry["label"],
                        "command": cmd,
                        "state": "available" if available else "unavailable",
                        "note": "" if available else "comando no instalado en este sistema",
                    })
            out[name] = {"label": spec["label"], "entries": entries}
        return out

    def launch(self, command: str) -> Dict[str, Any]:
        """Lanza una herramienta externa de la lista blanca, sin shell y sin bloquear."""
        allowed = {e["command"] for spec in SECTIONS.values() for e in spec["entries"]
                   if e.get("command")}
        if command not in allowed:
            return {"state": "rejected", "message": "comando fuera de la lista blanca"}
        if not self.allow_launch:
            return {"state": "rejected", "message": "lanzamiento deshabilitado en este contexto"}
        path = shutil.which(command)
        if path is None:
            return {"state": "unavailable", "message": "comando no instalado: " + command}
        try:
            subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return {"state": "error", "message": "no se pudo lanzar: " + type(exc).__name__}
        return {"state": "ok", "command": command}
