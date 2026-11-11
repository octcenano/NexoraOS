"""Nexora Kernel Extension: gestión segura de kernel y módulos.

Componentes:
  - KernelManager: versión del kernel, Secure Boot, capacidades de arranque.
  - ModuleManager: módulos cargados (/proc/modules), recomendaciones;
    NUNCA carga módulos: solo prepara propuestas (categoría protegida).
  - HardwareInterface: inventario de dispositivos por subsistema (udevadm
    si está disponible; si no, /sys).
  - KernelWatchdog: diagnóstico de controladores ausentes/problemáticos.
  - ExtensionAPI: la única puerta de entrada para Core y agentes.

Seguridad: ninguna operación privilegiada se ejecuta aquí. Las propuestas
de módulos exigen origen verificado (repositorio oficial de Arch) y
aprobación humana; NKE las documenta, no las ejecuta.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class KernelManager:
    def __init__(self, release: Optional[str] = None):
        self.release = release or platform.release()

    def status(self) -> Dict[str, Any]:
        from nexora.nke.capabilities import detect_capabilities
        caps = detect_capabilities(kernel_release=self.release)
        return {
            "release": self.release,
            "secure_boot": caps["secure_boot"],
            "psi": caps["can_psi_monitoring"],
            "cgroup_v2": caps["cgroup_v2"]["available"],
            "ebpf_bpffs": caps["ebpf"]["bpffs_mounted"],
            "cpufreq": caps["can_cpufreq_tuning"],
            "swap_devices": caps["swap"]["devices"],
        }


class ModuleManager:
    """Solo lectura. La carga de módulos es una propuesta, nunca una acción."""

    def __init__(self, proc_root: str = "/proc", modprobe_path: Optional[str] = None):
        self.proc = Path(proc_root)
        self.modprobe = modprobe_path or shutil.which("modprobe")

    def loaded(self) -> List[Dict[str, Any]]:
        mods: List[Dict[str, Any]] = []
        try:
            for line in (self.proc / "modules").read_text().splitlines():
                parts = line.split()
                if parts:
                    mods.append({"name": parts[0], "size": parts[1], "used_by": parts[3] if len(parts) > 3 else "0"})
        except OSError:
            pass
        return mods

    def is_loaded(self, name: str) -> bool:
        return any(m["name"] == name for m in self.loaded())

    def propose_load(self, name: str, reason: str) -> Dict[str, Any]:
        """Propuesta protegida: exige origen verificado y aprobación humana.

        NKE no ejecuta modprobe. La propuesta incluye el comando exacto y
        las comprobaciones que debe hacer el usuario.
        """
        if not name or not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("nombre de módulo inválido")
        return {
            "proposal": "load_kernel_module",
            "category": "protected",
            "module": name,
            "reason": reason,
            "requires": [
                "origen verificado (paquete oficial de Arch o DKMS propio del sistema)",
                "aprobación humana explícita",
                "ejecución manual: 'sudo modprobe " + name + "'",
            ],
            "executed_by_nke": False,
        }


class HardwareInterface:
    """Inventario de dispositivos por subsistema desde /sys (sin dependencias)."""

    def __init__(self, sys_root: str = "/sys"):
        self.sys = Path(sys_root)

    def devices(self, subsystem: str) -> List[str]:
        try:
            return sorted(p.name for p in (self.sys / "class" / subsystem).iterdir())
        except OSError:
            return []

    def summary(self) -> Dict[str, List[str]]:
        return {sub: self.devices(sub) for sub in ("net", "block", "drm", "backlight", "power_supply")}


class KernelWatchdog:
    """Diagnóstico de controladores: coredumps de kernel y módulos con fallos."""

    def __init__(self, proc_root: str = "/proc", sys_root: str = "/sys"):
        self.proc, self.sys = Path(proc_root), Path(sys_root)

    def diagnose(self) -> Dict[str, Any]:
        issues: List[str] = []
        # Módulos en estado de error no se exponen vía /proc/modules; el
        # indicador disponible sin privilegios es la cola de oops (dmesg
        # requiere permisos, así que se usa /proc/sys/kernel/... y contadores).
        try:
            tainted = (self.proc / "sys" / "kernel" / "tainted").read_text().strip()
            if tainted and tainted != "0":
                issues.append(f"kernel tainted (flags={tainted}): revisa dmesg")
        except OSError:
            pass
        hw = HardwareInterface(str(self.sys)).summary()
        if not hw.get("net"):
            issues.append("sin interfaces de red detectadas: posible controlador ausente")
        if not hw.get("drm"):
            issues.append("sin dispositivos DRM: gráficos sin controlador KMS cargado")
        return {"issues": issues, "hardware": hw}


class ExtensionAPI:
    """Única puerta de entrada para Nexora Core y agentes.

    Los agentes no acceden a /sys ni a /proc directamente: piden aquí.
    Devuelve información (solo lectura) y propuestas; nunca ejecuta
    operaciones privilegiadas.
    """

    def __init__(self):
        self.kernel = KernelManager()
        self.modules = ModuleManager()
        self.hardware = HardwareInterface()
        self.watchdog = KernelWatchdog()

    def request(self, agent_mode: str, query: str, **kwargs: Any) -> Dict[str, Any]:
        # Lista cerrada de consultas: nada de acceso libre a interfaces del kernel.
        if query == "kernel_status":
            return {"status": "ok", "data": self.kernel.status()}
        if query == "modules_loaded":
            return {"status": "ok", "data": self.modules.loaded()}
        if query == "hardware_summary":
            return {"status": "ok", "data": self.hardware.summary()}
        if query == "kernel_diagnose":
            return {"status": "ok", "data": self.watchdog.diagnose()}
        if query == "propose_module":
            return {"status": "proposal", "data": self.modules.propose_load(
                str(kwargs.get("module", "")), str(kwargs.get("reason", "solicitud de agente")))}
        return {"status": "denied", "reason": f"consulta desconocida: {query}"}
