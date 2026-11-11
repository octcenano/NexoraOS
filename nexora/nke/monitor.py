"""NKE Monitor: recopila métricas reales con sondeo adaptativo.

Lee PSI, memoria (MemAvailable/SwapFree), carga, temperaturas y procesos
desde /proc. El intervalo de sondeo se adapta: en reposo se duplica hasta
un máximo; con presión vuelve al mínimo. Así la huella propia es mínima.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nexora.nke.capabilities import detect_capabilities

MIN_INTERVAL_S = 2.0
MAX_INTERVAL_S = 60.0
IDLE_LOAD = 0.5          # load1 por debajo del cual el sistema está en reposo
IDLE_PSI_PCT = 5.0       # PSI avg10 por debajo del cual no hay presión


def read_meminfo(proc_root: Path) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {"MemAvailable_mb": None, "MemTotal_mb": None, "SwapFree_mb": None, "SwapTotal_mb": None}
    try:
        for line in (proc_root / "meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in ("MemAvailable", "MemTotal", "SwapFree", "SwapTotal"):
                out[f"{key}_mb"] = round(int(rest.strip().split()[0]) / 1024, 1)
    except (OSError, ValueError, IndexError):
        pass
    return out


def read_loadavg(proc_root: Path) -> Optional[Tuple[float, float, float]]:
    try:
        parts = (proc_root / "loadavg").read_text().split()
        return tuple(float(x) for x in parts[:3])  # type: ignore[return-value]
    except (OSError, ValueError, IndexError):
        return None


def read_psi(proc_root: Path) -> Dict[str, Optional[Dict[str, float]]]:
    from nexora.nke.capabilities import _proc_pressure
    return _proc_pressure(proc_root)


def top_processes(proc_root: Path, limit: int = 5) -> List[Dict[str, Any]]:
    """Procesos con más tiempo de CPU acumulado (utime+stime), solo lectura."""
    samples: List[Dict[str, Any]] = []
    try:
        entries = [p for p in proc_root.iterdir() if p.name.isdigit()]
    except OSError:
        return samples
    for p in entries:
        try:
            fields = (p / "stat").read_text().rsplit(") ", 1)[1].split()
            utime, stime = int(fields[11]), int(fields[12])
            comm = (p / "comm").read_text().strip()
            samples.append({"pid": int(p.name), "comm": comm, "cpu_ticks": utime + stime})
        except (OSError, ValueError, IndexError):
            continue
    samples.sort(key=lambda s: s["cpu_ticks"], reverse=True)
    return samples[:limit]


class NKMonitor:
    def __init__(self, proc_root: str = "/proc", sys_root: str = "/sys"):
        self.proc = Path(proc_root)
        self.sys = Path(sys_root)
        self.interval = MIN_INTERVAL_S
        self._samples = 0

    def sample(self) -> Dict[str, Any]:
        """Una pasada de métricas. Nunca lanza: lo ilegible es None."""
        mem = read_meminfo(self.proc)
        load = read_loadavg(self.proc)
        psi = read_psi(self.proc)
        self._samples += 1
        self._adapt_interval(load, psi)
        return {
            "mem": mem,
            "load": load,
            "psi": psi,
            "top_processes": top_processes(self.proc),
            "interval_s": self.interval,
        }

    def _adapt_interval(self, load, psi) -> None:
        busy = (load is not None and load[0] > IDLE_LOAD) or any(
            (v or {}).get("some", 0.0) > IDLE_PSI_PCT for v in (psi or {}).values()
        )
        if busy:
            self.interval = MIN_INTERVAL_S
        else:
            self.interval = min(self.interval * 2, MAX_INTERVAL_S)

    def capabilities(self) -> Dict[str, Any]:
        return detect_capabilities(str(self.proc), str(self.sys))
