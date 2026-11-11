"""Nexora Dashboard: métricas reales del sistema.

Fuentes: /proc, /sys y las utilidades del núcleo adaptativo. Ninguna cifra
se inventa: cada sección lleva un estado explícito (ok, unavailable, error).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from nexora.core.resources import inventory


def _read_meminfo() -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {"ram_total_gb": None, "ram_available_gb": None,
                                       "swap_total_gb": None, "swap_free_gb": None}
    try:
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                key, _, value = line.partition(":")
                parts = value.split()
                if not parts:
                    continue
                gb = round(int(parts[0]) / 1024**2, 2)
                if key == "MemTotal":
                    out["ram_total_gb"] = gb
                elif key == "MemAvailable":
                    out["ram_available_gb"] = gb
                elif key == "SwapTotal":
                    out["swap_total_gb"] = gb
                elif key == "SwapFree":
                    out["swap_free_gb"] = gb
    except (OSError, ValueError, IndexError):
        pass
    return out


def top_processes(limit: int = 6) -> Dict[str, Any]:
    """Procesos por RSS (desde /proc/[pid]/statm). Real o 'unavailable'."""
    if limit < 1 or limit > 50:
        raise ValueError("limit fuera de rango")
    rows: List[Dict[str, Any]] = []
    try:
        pids = [p for p in Path("/proc").iterdir() if p.name.isdigit()]
    except OSError:
        return {"state": "unavailable", "processes": []}
    page_kb = os.sysconf("SC_PAGE_SIZE") // 1024
    for proc in pids:
        try:
            comm = (proc / "comm").read_text().strip()
            rss_pages = int((proc / "statm").read_text().split()[1])
        except (OSError, ValueError, IndexError):
            continue
        rows.append({"pid": int(proc.name), "name": comm, "rss_mb": round(rss_pages * page_kb / 1024, 1)})
    rows.sort(key=lambda r: r["rss_mb"], reverse=True)
    return {"state": "ok", "processes": rows[:limit]}


def service_state(unit: str) -> Dict[str, Any]:
    """Estado de una unidad systemd real vía 'systemctl is-active'.

    Se ejecuta como lista de argumentos, sin shell: no hay inyección posible.
    """
    if not unit or not all(part.replace("-", "").replace("@", "").isalnum()
                           for part in unit.replace(".service", "").split(".")):
        return {"state": "error", "message": "nombre de unidad no válido"}
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return {"state": "unavailable", "message": "systemctl no está disponible"}
    try:
        proc = subprocess.run([systemctl, "is-active", unit], capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"state": "error", "message": "no se pudo consultar: " + type(exc).__name__}
    active = proc.stdout.decode().strip()
    return {"state": "ok", "unit": unit, "active": active}


def _section_unavailable(message: str) -> Dict[str, Any]:
    return {"state": "unavailable", "message": message, "data": None}


class DashboardModel:
    """Modelo del panel de información. Todo dato proviene de fuentes reales."""

    NEXORA_UNITS = ("nexora-watchdog.service", "nexora-nke.service")

    def __init__(self, engine=None, nke=None, coordinator=None):
        self.engine = engine
        self.nke = nke
        self.coordinator = coordinator

    def snapshot(self) -> Dict[str, Any]:
        mem = _read_meminfo()
        inv = inventory()
        snap: Dict[str, Any] = {}

        snap["cpu"] = ({"state": "ok", "data": {"cores": inv["cpu_cores"]}} if inv["cpu_cores"]
                       else _section_unavailable("no se pudo leer el número de núcleos"))
        snap["memory"] = ({"state": "ok", "data": mem} if mem["ram_total_gb"] is not None
                          else _section_unavailable("/proc/meminfo ilegible"))
        snap["gpu"] = ({"state": "ok", "data": inv["gpus"]} if inv["gpus"]
                       else {"state": "no_data", "data": [],
                             "message": "sin GPU dedicada detectada (o sin driver que la exponga)"})
        snap["temperatures"] = ({"state": "ok", "data": inv["temperatures_c"]} if inv["temperatures_c"]
                                else {"state": "no_data", "data": {},
                                      "message": "sin sensores de temperatura legibles (instale lm_sensors)"})
        snap["storage"] = ({"state": "ok", "data": {"free_gb": inv["storage_free_gb"]}}
                           if inv["storage_free_gb"] is not None
                           else _section_unavailable("no se pudo consultar el almacenamiento"))
        snap["network"] = ({"state": "ok", "data": {"interfaces": inv["network_interfaces"]}}
                           if inv["network_interfaces"]
                           else {"state": "no_data", "data": {"interfaces": []},
                                 "message": "sin interfaces de red detectadas"})
        snap["battery"] = ({"state": "ok", "data": inv["battery"]} if inv["battery"]
                           else {"state": "no_data", "data": None, "message": "sin batería (equipo de sobremesa)"})
        snap["top_processes"] = top_processes()
        snap["services"] = {"state": "ok", "data": [service_state(u) for u in self.NEXORA_UNITS]}

        if self.coordinator is not None:
            snap["core_activity"] = {"state": "ok", "data": self.coordinator.status()}
        else:
            snap["core_activity"] = {"state": "no_data", "data": None,
                                     "message": "Nexora Core no está en ejecución en este proceso"}
        if self.nke is not None:
            snap["nke_activity"] = {"state": "ok", "data": self.nke.status()}
        else:
            snap["nke_activity"] = {"state": "no_data", "data": None,
                                    "message": "NKE no está en ejecución en este proceso"}
        return snap
