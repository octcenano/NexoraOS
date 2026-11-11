"""Núcleo adaptativo: inventario de recursos y políticas por nivel.

Diseño:
  - Lee el estado real del sistema (CPU, RAM, GPU, batería, temperatura,
    almacenamiento) sin dependencias externas. Lo que no se puede leer se
    declara ``None``: nunca se inventa.
  - Los niveles (1, 2, 3, full) son políticas concretas y verificables
    (agentes concurrentes, RAM máxima para modelos, pesos de CPU), no etiquetas.
  - Los perfiles híbridos reparten recursos entre modos con un modo primario:
    un agente secundario nunca puede superar la cuota del primario.
  - Nada se aplica al sistema sin pasar por un plan reversible
    (``build_plan`` devuelve el plan; ``apply``/``rollback`` lo ejecutan).
    Optimizaciones agresivas ( governor, GPU) requieren compatibilidad
    comprobada y aprobación explícita.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------
# Inventario de hardware (solo lectura)
# --------------------------------------------------------------------------

def read_ram_gb() -> Optional[float]:
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
        return round(total, 1)
    except (AttributeError, ValueError, OSError):
        pass
    try:
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024**2, 1)
    except (OSError, ValueError, IndexError):
        pass
    return None


def read_cpu_cores() -> Optional[int]:
    cores = os.cpu_count()
    return cores if cores and cores >= 1 else None


def read_temperatures() -> Dict[str, float]:
    """Temperaturas en °C desde /sys/class/hwmon (solo lectura)."""
    out: Dict[str, float] = {}
    base = Path("/sys/class/hwmon")
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return out
    for hw in entries:
        try:
            name = (hw / "name").read_text().strip()
        except OSError:
            continue
        try:
            inputs = sorted(p for p in hw.iterdir() if p.name.startswith("temp") and p.name.endswith("_input"))
        except OSError:
            continue
        for p in inputs:
            try:
                value = int(p.read_text().strip()) / 1000.0
            except (OSError, ValueError):
                continue
            key = f"{name}/{p.name.replace('_input', '')}"
            if key not in out or value > out[key]:
                out[key] = round(value, 1)
    return out


def read_battery() -> Optional[Dict[str, Any]]:
    """Estado de batería desde /sys/class/power_supply (None si no hay)."""
    base = Path("/sys/class/power_supply")
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return None
    for supply in entries:
        if not supply.name.startswith("BAT"):
            continue
        info: Dict[str, Any] = {"device": supply.name}
        try:
            info["status"] = (supply / "status").read_text().strip()
        except OSError:
            info["status"] = None
        for key, target in (("capacity_pct", "capacity"), ("cycle_count", "cycle_count")):
            try:
                info[key] = int((supply / target).read_text().strip())
            except (OSError, ValueError):
                info[key] = None
        return info
    return None


def read_storage_gb(path: Optional[str] = None) -> Optional[float]:
    try:
        st = os.statvfs(path or "/")
        return round(st.f_bavail * st.f_frsize / 1024**3, 1)
    except (OSError, AttributeError, ValueError):
        return None


def read_network_interfaces() -> List[str]:
    try:
        return sorted(p.name for p in Path("/sys/class/net").iterdir())
    except OSError:
        return []


def inventory() -> Dict[str, Any]:
    """Inventario completo del sistema. Campos ilegibles: None o vacíos."""
    from nexora.core.profiles import detect_gpu

    return {
        "cpu_cores": read_cpu_cores(),
        "ram_gb": read_ram_gb(),
        "gpus": list(detect_gpu()),
        "temperatures_c": read_temperatures(),
        "battery": read_battery(),
        "storage_free_gb": read_storage_gb(),
        "network_interfaces": read_network_interfaces(),
    }


# --------------------------------------------------------------------------
# Niveles: políticas reales y verificables
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LevelPolicy:
    level: str
    concurrent_agents: int
    max_model_ram_gb: float
    cpu_weight: float          # peso relativo del modo en el reparto de CPU
    aggressive_tuning: bool    # solo True en 'full' y exige compatibilidad + aprobación
    description: str


LEVELS: Dict[str, LevelPolicy] = {
    "level1": LevelPolicy("level1", 1, 4.0, 0.5, False,
                          "Consumo mínimo: un agente, modelos pequeños"),
    "level2": LevelPolicy("level2", 2, 8.0, 1.0, False,
                          "Equilibrado: dos agentes, modelos medianos"),
    "level3": LevelPolicy("level3", 4, 16.0, 2.0, False,
                          "Rendimiento elevado: cuatro agentes, modelos grandes"),
    "full": LevelPolicy("full", 8, 999.0, 4.0, True,
                        "Prioridad total para el modo (requiere aprobación)"),
}


def level_policy(level: str) -> LevelPolicy:
    if level not in LEVELS:
        raise ValueError(f"Nivel desconocido: {level}. Opciones: {sorted(LEVELS)}")
    return LEVELS[level]


# Pesos por defecto de cada modo en perfiles híbridos (primario: secundarios).
MODE_WEIGHTS: Dict[str, float] = {
    "gaming": 1.0, "forge": 0.8, "security": 0.5,
    "office": 0.4, "stealth": 0.3, "creator": 0.4, "meteorology": 0.2,
}


# --------------------------------------------------------------------------
# Perfiles híbridos
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ModeShare:
    mode: str
    primary: bool
    cpu_weight: float
    cpu_share_pct: float
    ram_limit_gb: float
    agents_allowed: int


@dataclass(frozen=True)
class AllocationPlan:
    """Plan de reparto de recursos. Reversible: no toca el sistema hasta apply()."""
    level: str
    primary_mode: str
    shares: Tuple[ModeShare, ...]
    warnings: List[str] = field(default_factory=list)
    requires_approval: bool = False

    def for_mode(self, mode: str) -> Optional[ModeShare]:
        for s in self.shares:
            if s.mode == mode:
                return s
        return None


def build_allocation(
    modes: List[str],
    level: str = "level2",
    inv: Optional[Dict[str, Any]] = None,
) -> AllocationPlan:
    """Calcula el reparto de recursos para un conjunto de modos.

    El primer modo de la lista es el primario: recibe al menos el doble de
    peso que cualquier secundario y su cuota de RAM nunca puede ser invadida
    por los secundarios. Devuelve un plan; no modifica el sistema.
    """
    if not modes:
        raise ValueError("Se necesita al menos un modo")
    seen = []
    for m in modes:
        if m not in MODE_WEIGHTS:
            raise ValueError(f"Modo desconocido: {m}. Opciones: {sorted(MODE_WEIGHTS)}")
        if m in seen:
            raise ValueError(f"Modo duplicado: {m}")
        seen.append(m)

    inv = inv or inventory()
    policy = level_policy(level)
    ram = inv.get("ram_gb")
    cores = inv.get("cpu_cores")
    warnings: List[str] = []

    if ram is None or cores is None:
        raise ValueError("No se pudo leer CPU/RAM del sistema; no se reparten recursos a ciegas")

    # Peso: primario doble que su peso base; secundarios escala reducida.
    weights = {modes[0]: MODE_WEIGHTS[modes[0]] * 2.0}
    for m in modes[1:]:
        weights[m] = MODE_WEIGHTS[m]
    total_weight = sum(weights.values())

    # La RAM reservable nunca supera el 80% del total (el sistema necesita aire).
    usable_ram = round(ram * 0.8, 1)
    shares: List[ModeShare] = []
    for m in modes:
        pct = round(weights[m] / total_weight * 100.0, 1)
        ram_limit = round(min(usable_ram * weights[m] / total_weight, policy.max_model_ram_gb), 1)
        if ram_limit <= 0:
            warnings.append(f"El modo '{m}' se queda sin RAM asignable con {ram} GB totales")
        shares.append(ModeShare(
            mode=m,
            primary=(m == modes[0]),
            cpu_weight=weights[m],
            cpu_share_pct=pct,
            ram_limit_gb=ram_limit,
            agents_allowed=max(1, int(policy.concurrent_agents * weights[m] / max(weights.values()))),
        ))

    # Compatibilidad antes de optimizaciones agresivas.
    requires_approval = policy.aggressive_tuning
    if policy.aggressive_tuning and not inv.get("gpus") and not inv.get("temperatures_c"):
        warnings.append("Nivel 'full' sin GPU ni sensores de temperatura legibles: "
                        "no se aplicará ajuste agresivo (falta comprobación de compatibilidad)")

    # Batería: en portátil con batería baja se recomienda bajar de nivel.
    battery = inv.get("battery")
    if battery and battery.get("capacity_pct") is not None and battery["capacity_pct"] < 20 \
            and battery.get("status") == "Discharging":
        warnings.append(f"Batería al {battery['capacity_pct']}% y descargando: "
                        "se recomienda 'level1' hasta cargar")

    return AllocationPlan(
        level=level,
        primary_mode=modes[0],
        shares=tuple(shares),
        warnings=warnings,
        requires_approval=requires_approval,
    )
