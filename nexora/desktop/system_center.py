"""Nexora System Center: configuración del sistema.

Reutiliza las herramientas de XFCE y Linux (principio de no duplicación).
Cada sección declara entradas con comandos fijos y validados: la interfaz
nunca ejecuta comandos arbitrarios. Los estados son explícitos.

Las operaciones privilegiadas únicas (actualización del sistema) pasan por
pkexec con una lista blanca cerrada de acciones fijas: nunca se construyen
comandos a partir de entradas del usuario ni de modelos.
"""

from __future__ import annotations

import os
import pwd
import shutil
import subprocess
from typing import Any, Dict, List, Optional

# Acciones privilegiadas permitidas: lista cerrada, sin interpolación de
# argumentos. Cada acción es una tupla fija de argv que pkexec ejecutará
# tras la autenticación polkit del usuario.
PRIVILEGED_ACTIONS: Dict[str, Dict[str, Any]] = {
    "system_update": {
        "label": "Actualizar todos los paquetes (pacman -Syu)",
        "argv": ["pacman", "-Syu", "--noconfirm"],
        "requires": "pacman",
    },
}

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
        {"label": "Listado de cuentas del sistema", "command": None,
         "note": "solo lectura (cuentas detectadas); la creación y edición de cuentas requiere polkit y está fuera de la beta"},
    ]},
    "storage": {"label": "Almacenamiento", "entries": [
        {"label": "Gestor de archivos", "command": "thunar"},
    ]},
    "updates": {"label": "Actualizaciones", "entries": [
        {"label": "Paquetes con actualización pendiente", "command": None,
         "note": "consulta de solo lectura con pacman -Qu; la actualización se lanza vía pkexec desde la acción privilegiada"},
    ]},
    "services": {"label": "Servicios", "entries": [
        {"label": "Estado de servicios Nexora", "command": None,
         "note": "consultable en el Dashboard; la gestión requiere privilegios y está fuera de la beta"},
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


def list_users(passwd_path: Optional[str] = None) -> Dict[str, Any]:
    """Cuentas del sistema desde /etc/passwd (solo lectura).

    Devuelve cuentas humanas (uid >= 1000 o root) separadas de las de
    sistema. Nunca modifica nada.
    """
    path = passwd_path or "/etc/passwd"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        return {"state": "error", "message": "no se pudo leer " + path + ": " + type(exc).__name__}
    humans: List[Dict[str, Any]] = []
    system: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 7:
            continue
        name, _, uid_s, _, _, home, shell = parts[:7]
        try:
            uid = int(uid_s)
        except ValueError:
            continue
        entry = {"name": name, "uid": uid, "home": home, "shell": shell}
        if uid == 0 or uid >= 1000:
            humans.append(entry)
        else:
            system.append(entry)
    return {"state": "ok", "humans": humans, "system_count": len(system)}


def pending_updates(pacman_path: Optional[str] = None) -> Dict[str, Any]:
    """Paquetes con actualización pendiente vía pacman -Qu (solo lectura)."""
    path = pacman_path or shutil.which("pacman")
    if path is None:
        return {"state": "unavailable", "message": "pacman no está instalado en este sistema"}
    if not os.path.exists(path):
        return {"state": "unavailable", "message": "pacman no está disponible en: " + path}
    try:
        proc = subprocess.run([path, "-Qu"], capture_output=True, text=True,
                              timeout=30, shell=False)
    except subprocess.TimeoutExpired:
        return {"state": "error", "message": "pacman -Qu agotó el tiempo de espera"}
    except OSError as exc:
        return {"state": "error", "message": "no se pudo ejecutar pacman -Qu: " + type(exc).__name__}
    if proc.returncode != 0:
        return {"state": "error", "message": "pacman -Qu terminó con código " + str(proc.returncode)}
    packages = [line.split()[0] for line in proc.stdout.splitlines() if line.strip()]
    return {"state": "ok", "count": len(packages), "packages": packages}


class SystemCenter:
    """Secciones, lanzamiento validado y acciones privilegiadas cerradas."""

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
            section: Dict[str, Any] = {"label": spec["label"], "entries": entries}
            # Datos reales de solo lectura para las secciones que los tienen.
            if name == "users":
                section["data"] = list_users()
            elif name == "updates":
                section["data"] = pending_updates()
            out[name] = section
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

    def privileged_actions(self) -> Dict[str, Any]:
        """Catálogo de acciones privilegiadas cerradas y su disponibilidad."""
        actions = []
        for name, spec in PRIVILEGED_ACTIONS.items():
            req = shutil.which(spec["requires"]) is not None
            pk = shutil.which("pkexec") is not None
            actions.append({
                "name": name,
                "label": spec["label"],
                "argv": spec["argv"],
                "state": "available" if (req and pk) else "unavailable",
            })
        return {"state": "ok", "actions": actions}

    def launch_privileged(self, action: str, pkexec_path: Optional[str] = None) -> Dict[str, Any]:
        """Ejecuta una acción privilegiada de la lista cerrada vía pkexec.

        La autenticación la decide polkit (el usuario introduce su contraseña
        en el diálogo del sistema); esta interfaz nunca pide ni guarda
        contraseñas y nunca construye argv dinámicamente.
        """
        spec = PRIVILEGED_ACTIONS.get(action)
        if spec is None:
            return {"state": "rejected", "message": "acción privilegiada desconocida"}
        if not self.allow_launch:
            return {"state": "rejected", "message": "lanzamiento deshabilitado en este contexto"}
        pk_path = pkexec_path or shutil.which("pkexec")
        if pk_path is None:
            return {"state": "unavailable", "message": "pkexec no está disponible (se requiere polkit)"}
        if shutil.which(spec["requires"]) is None:
            return {"state": "unavailable", "message": spec["requires"] + " no está instalado"}
        try:
            subprocess.Popen([pk_path] + spec["argv"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return {"state": "error", "message": "no se pudo lanzar: " + type(exc).__name__}
        return {"state": "ok", "action": action, "message": "solicitado; polkit pedirá autenticación"}
