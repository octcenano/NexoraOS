"""Detección de capacidades reales del kernel y del hardware.

Todo se comprueba leyendo las interfaces reales. Una capacidad ausente se
declara como tal (False/None): NKE nunca presupone soporte.
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Dict, Optional


def _proc_pressure(root: Path) -> Dict[str, Optional[Dict[str, float]]]:
    """PSI: /proc/pressure/{cpu,memory,io}. None si el kernel no lo expone."""
    out: Dict[str, Optional[Dict[str, float]]] = {}
    for kind in ("cpu", "memory", "io"):
        path = root / "pressure" / kind
        data: Optional[Dict[str, float]] = None
        try:
            for line in path.read_text().splitlines():
                parts = line.split()
                if parts and parts[0] in ("some", "full"):
                    values = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in parts[1:] if "=" in kv}
                    data = data or {}
                    data[parts[0]] = values.get("avg10", 0.0)
        except (OSError, ValueError, IndexError):
            data = None
        out[kind] = data
    return out


def _cgroup_v2(root_sys: Path) -> Dict[str, Any]:
    """cgroups v2 unificado: controladores expuestos por el sistema."""
    info: Dict[str, Any] = {"available": False, "controllers": []}
    try:
        controllers = (root_sys / "fs" / "cgroup" / "cgroup.controllers").read_text().split()
        info["available"] = True
        info["controllers"] = sorted(controllers)
    except OSError:
        pass
    return info


def _ebpf(root_sys: Path) -> Dict[str, Any]:
    """eBPF: bpffs montado y política de BPF unprivileged (solo lectura)."""
    info: Dict[str, Any] = {"bpffs_mounted": False, "unprivileged_disabled": None}
    try:
        info["bpffs_mounted"] = (root_sys / "fs" / "bpf").is_dir()
    except OSError:
        pass
    try:
        info["unprivileged_disabled"] = int(
            (Path("/proc/sys/kernel/unprivileged_bpf_disabled")).read_text().strip()
        )
    except (OSError, ValueError):
        pass
    return info


def _cpufreq(root_sys: Path) -> Dict[str, Any]:
    """Gobernadores de CPU disponibles y actuales (None si no hay cpufreq)."""
    info: Dict[str, Any] = {"available": False, "governors": [], "current": []}
    cpu0 = root_sys / "devices" / "system" / "cpu" / "cpu0" / "cpufreq"
    try:
        info["governors"] = (cpu0 / "scaling_available_governors").read_text().split()
        info["available"] = bool(info["governors"])
        for cpu_dir in sorted((root_sys / "devices" / "system" / "cpu").glob("cpu[0-9]*")):
            gov = cpu_dir / "cpufreq" / "scaling_governor"
            try:
                info["current"].append((cpu_dir.name, gov.read_text().strip()))
            except OSError:
                continue
    except OSError:
        pass
    return info


def _swap(root_proc: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {"devices": [], "total_mb": 0}
    try:
        lines = (root_proc / "swaps").read_text().splitlines()[1:]
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                info["devices"].append({"path": parts[0], "type": parts[1], "size_mb": int(parts[3]) // 1024})
                info["total_mb"] += int(parts[3]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return info


def _secure_boot() -> Optional[bool]:
    """Estado de Secure Boot desde efivars (None si no es UEFI)."""
    base = Path("/sys/firmware/efi/efivars")
    try:
        for var in base.glob("SecureBoot-*"):
            raw = var.read_bytes()
            return bool(raw[-1]) if raw else None
    except OSError:
        pass
    return None


def detect_capabilities(
    proc_root: str = "/proc",
    sys_root: str = "/sys",
    kernel_release: Optional[str] = None,
) -> Dict[str, Any]:
    """Inventario de capacidades del kernel. Campos ilegibles: None o vacíos."""
    proc, sysfs = Path(proc_root), Path(sys_root)
    release = kernel_release or platform.release()
    caps: Dict[str, Any] = {
        "kernel_release": release,
        "psi": _proc_pressure(proc),
        "cgroup_v2": _cgroup_v2(sysfs),
        "ebpf": _ebpf(sysfs),
        "cpufreq": _cpufreq(sysfs),
        "swap": _swap(proc),
        "secure_boot": _secure_boot(),
    }
    caps["can_cgroup_limits"] = caps["cgroup_v2"]["available"] and all(
        c in caps["cgroup_v2"]["controllers"] for c in ("cpu", "memory")
    )
    caps["can_cpufreq_tuning"] = caps["cpufreq"]["available"]
    caps["can_psi_monitoring"] = any(v is not None for v in caps["psi"].values())
    return caps
