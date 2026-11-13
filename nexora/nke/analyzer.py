"""NKE Analyzer: interpreta métricas y produce hallazgos accionables.

Reglas explícitas y verificables (sin IA opaca): presión de memoria,
thrashing de swap, presión de CPU, presión de E/S y proceso dominante.
Cada hallazgo propone políticas candidatas con los parámetros concretos
que necesita el Safety Controller; decidir es tarea del Policy Engine,
que respeta categorías y permisos.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Umbrales (PSI avg10 en %, ratios adimensionales). Elegidos para avisar
# antes de la degradación, no para ruido.
MEM_PRESSURE_WARN = 30.0
MEM_PRESSURE_CRIT = 60.0
SWAP_THRASH_RATIO = 0.5     # swap libre < 50% de swap total con presión de mem
CPU_PRESSURE_WARN = 40.0
IO_PRESSURE_WARN = 30.0
LOW_MEM_FREE_MB = 512.0
AGENT_RAM_SHARE = 0.25      # techo del slice de nexora: 25% de la RAM total
AGENT_RAM_MIN_GB = 0.5


def _mem_limit_params(mem: Dict[str, Any]) -> Dict[str, str]:
    """Límite de RAM propuesto para el slice de nexora, derivado de MemTotal real."""
    total = mem.get("MemTotal_mb")
    if not total:
        return {}
    limit_gb = max(AGENT_RAM_MIN_GB, round(total * AGENT_RAM_SHARE / 1024, 1))
    return {"memory.max": f"{limit_gb}G"}


def analyze(sample: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    psi = sample.get("psi") or {}
    mem = sample.get("mem") or {}
    load = sample.get("load")

    mem_avg = (psi.get("memory") or {}).get("some")
    if mem_avg is not None and mem_avg >= MEM_PRESSURE_WARN:
        findings.append({
            "kind": "memory_pressure", "severity": "critical" if mem_avg >= MEM_PRESSURE_CRIT else "warning",
            "detail": f"presión de memoria (PSI some avg10 = {mem_avg}%)",
            "params": _mem_limit_params(mem),
            "suggests": ["reduce_agent_ram", "pause_secondary_agents"],
        })
    avail, total = mem.get("MemAvailable_mb"), mem.get("MemTotal_mb")
    if avail is not None and avail < LOW_MEM_FREE_MB:
        findings.append({
            "kind": "low_mem_available", "severity": "critical",
            "detail": f"memoria disponible baja: {avail} MB",
            "params": _mem_limit_params(mem),
            "suggests": ["reduce_agent_ram", "pause_secondary_agents"],
        })
    swap_total, swap_free = mem.get("SwapTotal_mb"), mem.get("SwapFree_mb")
    if mem_avg is not None and mem_avg >= MEM_PRESSURE_WARN and swap_total and swap_free is not None \
            and swap_free < swap_total * SWAP_THRASH_RATIO:
        findings.append({
            "kind": "swap_thrashing", "severity": "critical",
            "detail": f"swap ocupado ({swap_total - swap_free}/{swap_total} MB) con presión de memoria",
            "params": _mem_limit_params(mem),
            "suggests": ["reduce_agent_ram", "pause_secondary_agents"],
        })

    cpu_avg = (psi.get("cpu") or {}).get("some")
    if cpu_avg is not None and cpu_avg >= CPU_PRESSURE_WARN:
        findings.append({
            "kind": "cpu_pressure", "severity": "warning",
            "detail": f"presión de CPU (PSI some avg10 = {cpu_avg}%)",
            "suggests": ["deprioritize_secondary", "pause_secondary_agents"],
        })

    io_avg = (psi.get("io") or {}).get("some")
    if io_avg is not None and io_avg >= IO_PRESSURE_WARN:
        findings.append({
            "kind": "io_pressure", "severity": "warning",
            "detail": f"presión de E/S (PSI some avg10 = {io_avg}%)",
            "suggests": ["throttle_secondary_io"],
        })

    if load is not None and load[0] > 8.0:
        findings.append({
            "kind": "high_load", "severity": "warning",
            "detail": f"load1 = {load[0]}",
            "suggests": ["deprioritize_secondary"],
        })

    top = sample.get("top_processes") or []
    if top and cpu_avg is not None and cpu_avg >= CPU_PRESSURE_WARN and top[0]["cpu_ticks"] > 0:
        findings.append({
            "kind": "dominant_process", "severity": "info",
            "detail": f"proceso con más CPU acumulada: {top[0]['comm']} (pid {top[0]['pid']})",
            "suggests": [],
        })
    return findings
