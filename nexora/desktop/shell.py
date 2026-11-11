"""Nexora Shell: capa visual principal sobre xfce4-panel.

No duplica XFCE: declara la configuración del panel, el índice de
aplicaciones (archivos .desktop reales del sistema) y la búsqueda global.
Las notificaciones usan xfce4-notifyd a través de notify-send.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# Comandos integrados de Nexora expuestos en la búsqueda global (fijos,
# validados; nunca comandos arbitrarios del usuario).
NEXORA_COMMANDS = [
    {"name": "nexora health", "description": "Diagnóstico del sistema"},
    {"name": "nexora modes", "description": "Modos oficiales e intensidades"},
    {"name": "nexora audit", "description": "Auditoría defensiva de solo lectura"},
    {"name": "nexora status", "description": "Supervisión del core (watchdog)"},
    {"name": "nexora nke status", "description": "Estado del Nexora Kernel Engine"},
]

# Diseño del panel: nombres reales de plugins de xfce4-panel.
PANEL_LAYOUT = {
    "panel": 1,
    "position": "top",
    "left": [
        {"plugin": "whiskermenu", "label": "Menú de aplicaciones"},
        {"plugin": "launcher", "label": "Nexora Desktop", "command": "nexora-desktop"},
    ],
    "center": [
        {"plugin": "windowmenu", "label": "Ventanas"},
    ],
    "right": [
        {"plugin": "systray", "label": "Bandeja"},
        {"plugin": "pulseaudio", "label": "Audio (si está instalado)"},
        {"plugin": "power-manager-plugin", "label": "Energía (si está instalado)"},
        {"plugin": "clock", "label": "Reloj"},
    ],
}

QUICK_ACCESS = [
    {"label": "Dashboard", "module": "dashboard"},
    {"label": "Modos", "module": "mode_center"},
    {"label": "Kernel Engine", "module": "nke_control"},
    {"label": "Hub", "module": "hub"},
    {"label": "Sistema", "module": "system_center"},
]


def _desktop_dirs() -> List[Path]:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    dirs = [data_home]
    for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        if d.strip():
            dirs.append(Path(d.strip()))
    return dirs


class ApplicationIndex:
    """Índice de aplicaciones reales instaladas (archivos .desktop)."""

    def __init__(self, data_dirs: Optional[List[Path]] = None):
        self._dirs = data_dirs or _desktop_dirs()
        self._apps: Optional[List[Dict[str, Any]]] = None

    def scan(self) -> List[Dict[str, Any]]:
        if self._apps is not None:
            return self._apps
        apps: List[Dict[str, Any]] = []
        seen: set = set()
        for base in self._dirs:
            app_dir = base / "applications"
            try:
                entries = sorted(app_dir.glob("*.desktop"))
            except OSError:
                continue
            for path in entries:
                if path.name in seen:
                    continue
                seen.add(path.name)
                app = self._parse(path)
                if app:
                    apps.append(app)
        self._apps = apps
        return apps

    @staticmethod
    def _parse(path: Path) -> Optional[Dict[str, Any]]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        fields: Dict[str, str] = {}
        for line in text.splitlines():
            if line.startswith("[") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key in ("Name", "Exec", "Icon", "Categories", "NoDisplay", "Hidden") and key not in fields:
                fields[key] = value.strip()
        if fields.get("NoDisplay", "").lower() == "true" or fields.get("Hidden", "").lower() == "true":
            return None
        if not fields.get("Name") or not fields.get("Exec"):
            return None
        return {
            "name": fields["Name"],
            "exec": fields["Exec"],
            "icon": fields.get("Icon", ""),
            "categories": [c for c in fields.get("Categories", "").split(";") if c],
            "installed": shutil.which(fields["Exec"].split()[0]) is not None,
        }

    def search(self, term: str, limit: int = 12) -> List[Dict[str, Any]]:
        term = (term or "").strip().lower()
        if not term:
            return []
        results = []
        for app in self.scan():
            hay = app["name"].lower() + " " + " ".join(app["categories"]).lower()
            if term in hay:
                results.append(app)
                if len(results) >= limit:
                    break
        return results


class GlobalSearch:
    """Búsqueda global: aplicaciones instaladas + comandos Nexora."""

    def __init__(self, index: Optional[ApplicationIndex] = None):
        self.index = index or ApplicationIndex()

    def query(self, term: str, limit: int = 12) -> Dict[str, Any]:
        term = (term or "").strip()
        if not term:
            return {"state": "empty", "apps": [], "commands": []}
        apps = self.index.search(term, limit=limit)
        lowered = term.lower()
        commands = [c for c in NEXORA_COMMANDS
                    if lowered in c["name"] or lowered in c["description"].lower()]
        state = "ok" if (apps or commands) else "no_results"
        return {"state": state, "apps": apps, "commands": commands}


def notify(title: str, body: str) -> Dict[str, Any]:
    """Notificación de escritorio vía notify-send (xfce4-notifyd).

    Argumentos validados y sin shell: notify-send recibe exactamente dos
    argumentos de texto. Si no está instalado, se declara 'unavailable'.
    """
    if shutil.which("notify-send") is None:
        return {"state": "unavailable", "message": "notify-send no está instalado (paquete libnotify)"}
    try:
        proc = subprocess.run(["notify-send", str(title), str(body)],
                              capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"state": "error", "message": "no se pudo notificar: " + type(exc).__name__}
    if proc.returncode != 0:
        return {"state": "error", "message": "notify-send devolvió error"}
    return {"state": "ok"}


def workspaces(count: int = 4) -> Dict[str, Any]:
    """Escritorios virtuales: configuración declarativa para xfwm4.

    La aplicación real se hace con xfconf-query dentro de una sesión XFCE;
    aquí se declara el objetivo y se indica el requisito.
    """
    if count < 1 or count > 9:
        raise ValueError("Número de escritorios virtuales fuera de rango (1-9)")
    return {
        "state": "declared",
        "count": count,
        "note": "se aplica con xfconf-query dentro de una sesión XFCE activa",
        "xfconf": ["/general/workspace_count", "/general/workspace_names"],
    }
