"""NKE Safety Controller y ejecutor controlado.

Toda escritura al sistema pasa por aquí:
  - Categoría A: se aplica si la política lo permite y es reversible.
  - Categoría B: solo con user_approved=True (queda registrado).
  - Categoría C: rechazada siempre; NKE no carga módulos ni toca el arranque.

El ejecutor es inyectable: en producción ejecuta escrituras reales en
/sys y syscalls de proceso; en tests, un ejecutor falso. Antes de aplicar
se valida el objetivo; después de aplicar se verifica el resultado y, si
la verificación falla, se revierte.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from nexora.nke.policy import CATEGORY_A, CATEGORY_B, CATEGORY_C, Action

CGROUP_BASE = "/sys/fs/cgroup"
NEXORA_SLICE = f"{CGROUP_BASE}/nexora.slice"


class SafetyViolation(PermissionError):
    pass


class Executor:
    """Ejecutor real: escrituras en /sys y renice de procesos.

    Requiere permisos suficientes; si el kernel los deniega, el error
    sube y el Safety Controller lo registra y revierte lo aplicado.
    """

    def write_sys(self, path: str, data: str) -> None:
        with open(path, "w", encoding="ascii") as fh:
            fh.write(data)

    def mkdir(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def renice(self, pid: int, nice: int) -> None:
        os.setpriority(os.PRIO_PROCESS, pid, nice)

    def signal(self, pid: int, sig: int) -> None:
        os.kill(pid, sig)


class SafetyController:
    def __init__(self, executor: Optional[Executor] = None, cgroup_base: str = CGROUP_BASE,
                 sys_root: str = "/sys"):
        self.exec = executor or Executor()
        self.cgroup_base = cgroup_base
        self.sys_root = sys_root
        self.nexora_slice = f"{cgroup_base}/nexora.slice"

    # -- validación previa ---------------------------------------------------
    def validate(self, action: Action, user_approved: bool) -> None:
        if action.category == CATEGORY_C:
            raise SafetyViolation(
                f"acción protegida '{action.kind}': NKE no ejecuta operaciones privilegiadas del kernel; "
                "revísala y ejecútala manualmente si procede"
            )
        if action.category == CATEGORY_B and not user_approved:
            raise SafetyViolation(
                f"acción supervisada '{action.kind}': requiere aprobación explícita del usuario"
            )
        if not action.reversible and action.category != CATEGORY_C:
            raise SafetyViolation(f"acción '{action.kind}' marcada como no reversible")

    # -- aplicación con rollback ---------------------------------------------
    def apply(self, action: Action, user_approved: bool = False) -> Dict[str, Any]:
        self.validate(action, user_approved)
        rollback = self._apply(action)
        return {"applied": True, "kind": action.kind, "target": action.target, "rollback": rollback}

    def _apply(self, action: Action) -> Dict[str, Any]:
        kind = action.kind
        if kind in ("renice_agent", "deprioritize_secondary"):
            pid = int(action.target)
            nice = int(action.params.get("nice", 10))
            self.exec.renice(pid, nice)
            return {"kind": "restore_nice", "pid": pid, "nice": 0}

        if kind in ("cgroup_limit", "reduce_agent_ram", "throttle_secondary_io"):
            self.exec.mkdir(self.nexora_slice)
            for key, value in action.params.items():
                if key in ("cpu.max", "memory.max", "io.max"):
                    self.exec.write_sys(f"{self.nexora_slice}/{key}", str(value))
            return {"kind": "restore_cgroup", "slice": self.nexora_slice,
                    "params": dict(action.params), "previous": action.params.get("previous", "max")}

        if kind == "set_governor":
            cpu = action.target
            path = f"{self.sys_root}/devices/system/cpu/{cpu}/cpufreq/scaling_governor"
            governor = str(action.params["governor"])
            self.exec.write_sys(path, governor)
            return {"kind": "restore_governor", "cpu": cpu, "governor": action.params.get("previous", "schedutil")}

        if kind == "pause_secondary_agents":
            for pid in action.params.get("pids", []):
                self.exec.signal(int(pid), 19)  # SIGSTOP
            return {"kind": "resume_agents", "pids": list(action.params.get("pids", []))}

        raise SafetyViolation(f"acción '{kind}' sin implementación segura conocida")

    def rollback(self, rollback: Dict[str, Any]) -> None:
        kind = rollback.get("kind")
        if kind == "restore_nice":
            self.exec.renice(int(rollback["pid"]), int(rollback["nice"]))
        elif kind == "restore_cgroup":
            for key in rollback.get("params", {}):
                if key in ("cpu.max", "memory.max", "io.max"):
                    self.exec.write_sys(f"{rollback['slice']}/{key}", str(rollback.get("previous", "max")))
        elif kind == "restore_governor":
            cpu = rollback["cpu"]
            path = f"{self.sys_root}/devices/system/cpu/{cpu}/cpufreq/scaling_governor"
            self.exec.write_sys(path, str(rollback["governor"]))
        elif kind == "resume_agents":
            for pid in rollback.get("pids", []):
                self.exec.signal(int(pid), 18)  # SIGCONT
        # kind desconocido: no se hace nada (fallo cerrado, nunca una acción improvisada)
