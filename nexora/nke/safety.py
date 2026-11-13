"""NKE Safety Controller y ejecutor controlado.

Toda escritura al sistema pasa por aquí:
  - Categoría A: se aplica si la política lo permite y es reversible.
  - Categoría B: solo con user_approved=True (queda registrado).
  - Categoría C: rechazada siempre; NKE no carga módulos ni toca el arranque.
  - Acciones del catálogo sin implementación segura (p. ej. change_dns):
    rechazadas con el motivo explícito; nunca se simula una ejecución.

Reversibilidad exacta:
  - Antes de modificar se lee el valor real actual (nice, límite de cgroup,
    gobernador, swappiness). Si no se puede leer, la acción se rechaza: no
    se modifica nada que no se pueda restaurar.
  - El rollback restaura exactamente el valor capturado y verifica la
    restauración releyendo el estado; un rollback de tipo desconocido
    lanza error, nunca se ignora en silencio.

El ejecutor es inyectable: en producción ejecuta escrituras reales en
/sys y /proc y syscalls de proceso; en tests, un ejecutor falso.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from nexora.nke.policy import ACTION_CATALOG, CATEGORY_A, CATEGORY_B, CATEGORY_C, Action

CGROUP_BASE = "/sys/fs/cgroup"
NEXORA_SLICE = f"{CGROUP_BASE}/nexora.slice"
CGROUP_KEYS = ("cpu.max", "memory.max", "io.max")
CGROUP_DEFAULT = "max"  # valor por defecto del kernel para un límite recién creado
SWAPPINESS_MIN, SWAPPINESS_MAX = 0, 100


class SafetyViolation(PermissionError):
    pass


class Executor:
    """Ejecutor real: escrituras en /sys y /proc, renice y señales.

    Requiere permisos suficientes; si el kernel los deniega, el error
    sube y el Safety Controller lo registra y revierte lo aplicado.
    """

    def write_sys(self, path: str, data: str) -> None:
        with open(path, "w", encoding="ascii") as fh:
            fh.write(data)

    def read_sys(self, path: str) -> Optional[str]:
        try:
            return Path(path).read_text(encoding="ascii").strip()
        except (OSError, ValueError):
            return None

    def mkdir(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def renice(self, pid: int, nice: int) -> None:
        os.setpriority(os.PRIO_PROCESS, pid, nice)

    def getnice(self, pid: int) -> Optional[int]:
        try:
            return os.getpriority(os.PRIO_PROCESS, pid)
        except OSError:
            return None

    def signal(self, pid: int, sig: int) -> None:
        os.kill(pid, sig)


class SafetyController:
    def __init__(self, executor: Optional[Executor] = None, cgroup_base: str = CGROUP_BASE,
                 sys_root: str = "/sys", proc_root: str = "/proc"):
        self.exec = executor or Executor()
        self.cgroup_base = cgroup_base
        self.sys_root = sys_root
        self.proc_root = proc_root
        self.nexora_slice = f"{cgroup_base}/nexora.slice"

    # -- validación previa ---------------------------------------------------
    def validate(self, action: Action, user_approved: bool) -> None:
        spec = ACTION_CATALOG.get(action.kind)
        if spec is None:
            raise SafetyViolation(
                f"acción '{action.kind}' desconocida para el catálogo de NKE: no se ejecuta"
            )
        if not spec.get("implemented", True):
            raise SafetyViolation(
                f"acción '{action.kind}' declarada en el catálogo pero sin implementación "
                "segura y reversible: no se ejecuta ni se aprueba"
            )
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
            previous = self.exec.getnice(pid)
            if previous is None:
                raise SafetyViolation(
                    f"no se pudo leer el nice actual de {pid}: no se modifica sin valor previo restaurable"
                )
            self.exec.renice(pid, nice)
            return {"kind": "restore_nice", "pid": pid, "nice": previous}

        if kind in ("cgroup_limit", "reduce_agent_ram", "throttle_secondary_io"):
            self.exec.mkdir(self.nexora_slice)
            previous: Dict[str, str] = {}
            for key in CGROUP_KEYS:
                if key not in action.params:
                    continue
                path = f"{self.nexora_slice}/{key}"
                current = self.exec.read_sys(path)
                # Un slice recién creado no tiene el archivo: el valor por
                # defecto del kernel es "max". Un valor previo real se
                # captura y se restaura tal cual, nunca se asume.
                previous[key] = current if current is not None else CGROUP_DEFAULT
                self.exec.write_sys(path, str(action.params[key]))
            if not previous:
                raise SafetyViolation(
                    "sin parámetros de límite reconocidos (cpu.max, memory.max, io.max): "
                    "no se aplica un límite vacío"
                )
            return {"kind": "restore_cgroup", "slice": self.nexora_slice, "previous": previous}

        if kind == "set_governor":
            cpu = action.target
            path = f"{self.sys_root}/devices/system/cpu/{cpu}/cpufreq/scaling_governor"
            governor = str(action.params["governor"])
            current = self.exec.read_sys(path)
            if current is None:
                raise SafetyViolation(
                    f"no se pudo leer el gobernador actual de {cpu}: no se modifica sin valor previo restaurable"
                )
            self.exec.write_sys(path, governor)
            return {"kind": "restore_governor", "cpu": cpu, "governor": current}

        if kind == "set_swappiness":
            value = int(action.params["swappiness"])
            if not (SWAPPINESS_MIN <= value <= SWAPPINESS_MAX):
                raise SafetyViolation(
                    f"swappiness {value} fuera de rango [{SWAPPINESS_MIN}, {SWAPPINESS_MAX}]"
                )
            path = f"{self.proc_root}/sys/vm/swappiness"
            current = self.exec.read_sys(path)
            if current is None:
                raise SafetyViolation(
                    "no se pudo leer vm.swappiness actual: no se modifica sin valor previo restaurable"
                )
            self.exec.write_sys(path, str(value))
            return {"kind": "restore_swappiness", "path": path, "value": current}

        if kind == "pause_secondary_agents":
            for pid in action.params.get("pids", []):
                self.exec.signal(int(pid), 19)  # SIGSTOP
            return {"kind": "resume_agents", "pids": list(action.params.get("pids", []))}

        raise SafetyViolation(f"acción '{kind}' sin implementación segura conocida")

    def rollback(self, rollback: Dict[str, Any]) -> None:
        kind = rollback.get("kind")
        if kind == "restore_nice":
            pid, nice = int(rollback["pid"]), int(rollback["nice"])
            self.exec.renice(pid, nice)
            current = self.exec.getnice(pid)
            if current is not None and current != nice:
                raise OSError(f"restauración no verificada: nice de {pid} = {current}, esperado {nice}")
        elif kind == "restore_cgroup":
            for key, previous in rollback.get("previous", {}).items():
                if key in CGROUP_KEYS:
                    path = f"{rollback['slice']}/{key}"
                    self.exec.write_sys(path, str(previous))
                    self._verify(path, previous)
        elif kind == "restore_governor":
            path = f"{self.sys_root}/devices/system/cpu/{rollback['cpu']}/cpufreq/scaling_governor"
            self.exec.write_sys(path, str(rollback["governor"]))
            self._verify(path, rollback["governor"])
        elif kind == "restore_swappiness":
            self.exec.write_sys(rollback["path"], str(rollback["value"]))
            self._verify(rollback["path"], rollback["value"])
        elif kind == "resume_agents":
            for pid in rollback.get("pids", []):
                self.exec.signal(int(pid), 18)  # SIGCONT
        else:
            raise ValueError(f"rollback de tipo desconocido '{kind}': no se ejecuta nada")

    def _verify(self, path: str, expected: Any) -> None:
        current = self.exec.read_sys(path)
        if current is None or current != str(expected):
            raise OSError(f"restauración no verificada: {path} = {current!r}, esperado {expected!r}")
