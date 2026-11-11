"""Perfiles híbridos: el hardware sugiere una base segura; el usuario manda."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

TIERS = ("compact", "balanced", "expanded")

# Límites orientativos por perfil (propuesta de diseño, no medidos).
TIER_LIMITS = {
    "compact": {"concurrent_agents": 1, "local_model_hint": "hasta ~3B parámetros, cuantizado"},
    "balanced": {"concurrent_agents": 2, "local_model_hint": "hasta ~8B parámetros, cuantizado"},
    "expanded": {"concurrent_agents": 4, "local_model_hint": "modelos de 14B+ según VRAM/RAM"},
}


@dataclass(frozen=True)
class HardwareInfo:
    cpu_cores: int
    ram_gb: float
    source: str
    gpus: tuple[str, ...] = ()
    storage_free_gb: Optional[float] = None


def detect_gpu() -> tuple:
    """GPUs deducibles de /sys/class/drm (fabricante). Sin dependencias externas."""
    vendors = {"0x10de": "NVIDIA", "0x8086": "Intel", "0x1002": "AMD", "0x1022": "AMD"}
    base = Path("/sys/class/drm")
    found: list = []
    try:
        entries = sorted(os.listdir(base))
    except OSError:
        return ()
    for entry in entries:
        # tarjetas reales: card0, card1... (no card0-DP-1, card0-HDMI-A-1...)
        if not entry.startswith("card") or not entry[4:].isdigit():
            continue
        try:
            vendor = (base / entry / "device" / "vendor").read_text().strip().lower()
        except OSError:
            continue
        name = vendors.get(vendor, vendor)
        if name not in found:
            found.append(name)
    return tuple(found)


def detect_storage_gb(path: Optional[Path] = None) -> Optional[float]:
    """GB libres en el sistema de ficheros de la ruta indicada (por defecto ~)."""
    try:
        st = os.statvfs(str(path or Path.home()))
        return round(st.f_bavail * st.f_frsize / 1024**3, 1)
    except (OSError, AttributeError, ValueError):
        return None


def detect_hardware() -> Optional[HardwareInfo]:
    """Detecta CPU, RAM, GPU y almacenamiento sin dependencias externas. None si no puede."""
    cores = os.cpu_count()
    ram_gb = None
    try:
        ram_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (AttributeError, ValueError, OSError):
        try:
            with open("/proc/meminfo", encoding="ascii") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        ram_gb = int(line.split()[1]) / 1024**2
                        break
        except OSError:
            pass
    if not cores or not ram_gb or ram_gb <= 0:
        return None
    return HardwareInfo(
        cpu_cores=cores,
        ram_gb=round(ram_gb, 1),
        source="os",
        gpus=detect_gpu(),
        storage_free_gb=detect_storage_gb(),
    )


def suggest_tier(cpu_cores: int, ram_gb: float) -> str:
    if ram_gb <= 4 or cpu_cores <= 2:
        return "compact"
    if ram_gb >= 16 and cpu_cores >= 8:
        return "expanded"
    return "balanced"


def calculate_hybrid_profile(
    strategy: str,
    cpu_cores: int,
    ram_gb: float,
    manual_limits: Optional[dict] = None,
) -> dict:
    """Resuelve el perfil.

    strategy:
      - ``auto``: aplica la sugerencia del hardware.
      - ``compact`` | ``balanced`` | ``expanded``: el usuario fija el perfil.
      - ``manual``: límites definidos por el usuario (``manual_limits``).
    """
    if cpu_cores < 1 or ram_gb <= 0:
        raise ValueError("Los valores de hardware deben ser positivos")
    if strategy not in ("auto", "manual") + TIERS:
        raise ValueError(f"Estrategia de perfil desconocida: {strategy}")

    suggested = suggest_tier(cpu_cores, ram_gb)

    if strategy == "manual":
        return {
            "name": "user-controlled",
            "strategy": "manual",
            "suggested": suggested,
            "limits": dict(manual_limits or {}),
            "note": "Límites definidos por el usuario; el sistema no aplica ninguno por su cuenta.",
        }

    tier = suggested if strategy == "auto" else strategy
    profile = {
        "name": tier,
        "strategy": "auto" if strategy == "auto" else "manual-tier",
        "suggested": suggested,
        "limits": dict(TIER_LIMITS[tier]),
        "note": "Sugerencia automática; los ajustes del usuario tienen prioridad.",
    }
    if TIERS.index(tier) > TIERS.index(suggested):
        profile["warning"] = (
            f"El perfil '{tier}' supera lo recomendado para este hardware ('{suggested}'). "
            "Puedes revertirlo con --profile auto."
        )
    return profile
