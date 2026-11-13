"""Optimizador de red de NGNE: colas fq-codel/CAKE y DNS con consentimiento.

Diseño:
  - Cambiar la cola del kernel (tc qdisc) es una acción privilegiada: se
    ejecuta con pkexec (polkit autentica al usuario). El argv es fijo y
    validado: nunca se construye un comando de shell con entrada libre.
  - Restauración exacta: antes de tocar la cola se lee la cola real con
    'tc qdisc show dev <iface>'. Si la cola actual tiene parámetros propios
    que no se pueden reproducir (por ejemplo htb), no se toca nada. Tras
    restaurar se vuelve a leer y se verifica; una restauración no verificada
    se declara como error, nunca como éxito.
  - DNS solo con consentimiento explícito (user_approved=True) y con
    servidores pasados por el usuario (validados como IP). NGNE nunca elige
    servidores DNS por su cuenta. Los servidores previos se capturan y la
    restauración se verifica.
  - Gestión de tráfico: la cola activa (fq-codel o CAKE) gestiona el
    bufferbloat de forma justa para TODO el tráfico; no existe priorización
    de 'todo UDP'. La priorización por puertos concretos del juego queda
    como propuesta y exige aprobación; no se aplica en la beta.
  - El ejecutor de subprocess es inyectable para probar sin red ni root.
"""

from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

Runner = Callable[..., subprocess.CompletedProcess]

UNAVAILABLE = "unavailable"
CONFIRMATION_REQUIRED = "confirmation_required"

# Colas que sabemos restaurar con garantía (estado por defecto o cola simple).
SUPPORTED_QDISCS = ("noqueue", "pfifo_fast", "fq_codel", "cake")
APPLICABLE_QDISCS = ("fq_codel", "cake")

QDISC_PARAM_KEYS: Dict[str, tuple] = {
    "cake": ("bandwidth", "diffserv", "rtt"),
    "fq_codel": ("target", "interval", "limit"),
}


class QueueOptimizer:
    """Cambio de cola (qdisc) por interfaz con verificación y restauración."""

    def __init__(
        self,
        runner: Optional[Runner] = None,
        tc_path: Optional[str] = None,
        pkexec_path: Optional[str] = None,
        sys_net: str = "/sys/class/net",
        clock: Callable[[], float] = time.monotonic,
        max_history: int = 100,
    ):
        self._runner: Runner = runner or subprocess.run
        self._tc_path = tc_path
        self._pkexec_path = pkexec_path
        self.sys_net = sys_net
        self._clock = clock
        self.max_history = max_history
        self._history: List[Dict[str, Any]] = []
        self._seq = 0

    # -- rutas de herramientas -------------------------------------------------
    def tc_path(self) -> Optional[str]:
        return self._tc_path or shutil.which("tc")

    def pkexec_path(self) -> Optional[str]:
        return self._pkexec_path or shutil.which("pkexec")

    # -- observación -------------------------------------------------------------
    def current_qdisc(self, iface: str) -> Dict[str, Any]:
        """Lee la cola real de la interfaz con 'tc qdisc show' (solo lectura)."""
        tc = self.tc_path()
        if not tc:
            return {"state": UNAVAILABLE, "note": "tc no está instalado (paquete iproute2)"}
        try:
            proc = self._runner([tc, "qdisc", "show", "dev", iface],
                                capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "error", "note": f"tc falló: {type(exc).__name__}"}
        if proc.returncode != 0:
            detail = ((proc.stderr or "").strip() or "(sin stderr)")
            return {"state": "error",
                    "note": "tc qdisc show terminó con código " + str(proc.returncode)
                            + ": " + detail}
        raw = (proc.stdout or "").strip()
        kind = None
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "qdisc":
                kind = parts[1]
                break
        if kind is None:
            return {"state": "error", "note": "salida de tc no interpretable", "raw": raw}
        return {"state": "ok", "kind": kind, "raw": raw}

    def compatibility(self, iface: str) -> Dict[str, Any]:
        """Qué se puede hacer aquí, con datos reales y sin efectos."""
        cur = self.current_qdisc(iface)
        tc = bool(self.tc_path())
        pk = bool(self.pkexec_path())
        iface_exists = os.path.exists(os.path.join(self.sys_net, iface))
        return {
            "iface": iface,
            "iface_exists": iface_exists,
            "tc": tc,
            "pkexec": pk,
            "current": cur,
            "applicable": list(APPLICABLE_QDISCS),
            "state": "ok" if (tc and pk and iface_exists and cur.get("state") == "ok")
                     else UNAVAILABLE,
        }

    # -- aplicación ----------------------------------------------------------------
    def apply_qdisc(self, iface: str, kind: str, params: Optional[Dict[str, Any]] = None,
                    user_approved: bool = False) -> Dict[str, Any]:
        """Aplica fq-codel o CAKE en la interfaz con consentimiento y verificación."""
        if kind not in APPLICABLE_QDISCS:
            return {"state": "rejected",
                    "note": "cola no soportada: " + str(kind)
                            + "; opciones: " + ", ".join(APPLICABLE_QDISCS)}
        params = dict(params or {})
        allowed = QDISC_PARAM_KEYS[kind]
        unknown = [k for k in params if k not in allowed]
        if unknown:
            return {"state": "rejected",
                    "note": "parámetros desconocidos para " + kind + ": "
                            + ", ".join(sorted(unknown))
                            + "; permitidos: " + ", ".join(allowed)}
        if not os.path.exists(os.path.join(self.sys_net, iface)):
            return {"state": "rejected", "note": "interfaz desconocida: " + iface}
        if not user_approved:
            return {"state": CONFIRMATION_REQUIRED,
                    "note": "cambiar la cola del kernel es una acción privilegiada: "
                            "requiere confirmación explícita",
                    "action": {"kind": kind, "iface": iface, "params": params}}
        tc = self.tc_path()
        pk = self.pkexec_path()
        if not tc or not pk:
            return {"state": UNAVAILABLE, "note": "se requiere tc (iproute2) y pkexec (polkit)"}
        prev = self.current_qdisc(iface)
        if prev.get("state") != "ok":
            return {"state": "error",
                    "note": "no se pudo leer la cola actual con garantía; no se toca nada",
                    "detail": prev.get("note", "")}
        if prev["kind"] not in SUPPORTED_QDISCS:
            return {"state": "rejected",
                    "note": "la cola actual (" + prev["kind"] + ") tiene parámetros propios "
                            "que no se pueden restaurar con garantía; no se toca nada"}
        argv = [pk, tc, "qdisc", "replace", "dev", iface, "root", kind]
        if kind == "cake":
            if "bandwidth" in params:
                argv += ["bandwidth", str(params["bandwidth"])]
            if "diffserv" in params:
                argv += [str(params["diffserv"])]
            if "rtt" in params:
                argv += ["rtt", str(params["rtt"])]
        else:
            for key in ("target", "interval", "limit"):
                if key in params:
                    argv += [key, str(params[key])]
        try:
            proc = self._runner(argv, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "error",
                    "note": f"no se pudo aplicar la cola: {type(exc).__name__}"}
        if proc.returncode != 0:
            return {"state": "error",
                    "note": "tc terminó con código " + str(proc.returncode) + ": "
                            + (proc.stderr or "").strip()}
        cur = self.current_qdisc(iface)
        self._seq += 1
        mod: Dict[str, Any] = {
            "id": f"ngne-{self._seq}", "type": "qdisc", "iface": iface,
            "kind": kind, "params": params,
            "previous_kind": prev["kind"], "previous_raw": prev["raw"],
            "time": self._clock(),
        }
        if cur.get("state") == "ok" and cur.get("kind") == kind:
            mod["state"] = "applied"
            self._history.append(mod)
            if len(self._history) > self.max_history:
                self._prune()
            return {"state": "ok", "modification": dict(mod), "verified": True}
        # la verificación falló: restauración inmediata del estado previo
        restore = self._restore_mod(mod)
        return {"state": "error",
                "note": "la cola no quedó verificada tras aplicar; se restauró el estado previo",
                "restore": restore}

    # -- restauración -------------------------------------------------------------
    def _restore_mod(self, mod: Dict[str, Any]) -> Dict[str, Any]:
        tc = self.tc_path()
        pk = self.pkexec_path()
        if not tc or not pk:
            return {"state": UNAVAILABLE, "note": "sin tc o sin pkexec: no se puede restaurar"}
        iface = mod["iface"]
        prev_kind = mod["previous_kind"]
        if prev_kind == "noqueue":
            argv = [pk, tc, "qdisc", "del", "dev", iface, "root"]
        else:
            argv = [pk, tc, "qdisc", "replace", "dev", iface, "root", prev_kind]
        try:
            proc = self._runner(argv, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "error", "note": f"restauración fallida: {type(exc).__name__}"}
        if proc.returncode != 0:
            return {"state": "error",
                    "note": "restauración fallida, código " + str(proc.returncode) + ": "
                            + (proc.stderr or "").strip()}
        cur = self.current_qdisc(iface)
        if cur.get("state") == "ok" and cur.get("kind") == prev_kind:
            mod["state"] = "reverted"
            return {"state": "ok", "verified": True}
        return {"state": "error", "note": "la restauración no se pudo verificar"}

    def _prune(self) -> None:
        closed = [m for m in self._history if m.get("state") != "applied"]
        applied = [m for m in self._history if m.get("state") == "applied"]
        keep = applied + closed
        self._history = keep[-self.max_history:]

    def undo_last(self) -> Dict[str, Any]:
        """Deshace la última modificación aplicada, con verificación."""
        applied = [m for m in self._history if m.get("state") == "applied"]
        if not applied:
            return {"state": UNAVAILABLE, "note": "no hay modificaciones que deshacer"}
        mod = applied[-1]
        result = self._restore_mod(mod)
        return {"state": result["state"], "modification": dict(mod), "restore": result}

    def modifications(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in self._history]


class DnsOptimizer:
    """Cambio de DNS por enlace con resolvectl: solo con consentimiento explícito.

    Los servidores previos se capturan de resolv.conf; la restauración se
    verifica releyendo la configuración del enlace. NGNE nunca elige
    servidores: el usuario debe pasarlos y aprobar el cambio.
    """

    def __init__(
        self,
        runner: Optional[Runner] = None,
        resolvectl_path: Optional[str] = None,
        pkexec_path: Optional[str] = None,
        resolv_path: str = "/etc/resolv.conf",
        clock: Callable[[], float] = time.monotonic,
        max_history: int = 50,
    ):
        self._runner: Runner = runner or subprocess.run
        self._resolvectl_path = resolvectl_path
        self._pkexec_path = pkexec_path
        self.resolv_path = resolv_path
        self._clock = clock
        self.max_history = max_history
        self._history: List[Dict[str, Any]] = []
        self._seq = 0

    def resolvectl_path(self) -> Optional[str]:
        return self._resolvectl_path or shutil.which("resolvectl")

    def pkexec_path(self) -> Optional[str]:
        return self._pkexec_path or shutil.which("pkexec")

    def current(self) -> Dict[str, Any]:
        """Servidores DNS declarados en resolv.conf (solo lectura)."""
        try:
            with open(self.resolv_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            return {"state": UNAVAILABLE, "note": "no se pudo leer " + self.resolv_path,
                    "servers": []}
        servers: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("nameserver"):
                parts = line.split()
                if len(parts) >= 2:
                    servers.append(parts[1])
        return {"state": "ok", "servers": servers, "source": self.resolv_path}

    @staticmethod
    def _valid_servers(servers: List[str]) -> Optional[str]:
        if not servers:
            return "lista de servidores vacía: para volver a la configuración anterior usa undo_last"
        for server in servers:
            try:
                ipaddress.ip_address(str(server))
            except ValueError:
                return "servidor DNS no válido (no es una IP): " + str(server)
        return None

    def set_servers(self, iface: str, servers: List[str],
                    user_approved: bool = False) -> Dict[str, Any]:
        """Fija los DNS del enlace con resolvectl; exige IP válidas y consentimiento."""
        if not iface or not str(iface).strip():
            return {"state": "rejected", "note": "interfaz no indicada"}
        invalid = self._valid_servers(list(servers or []))
        if invalid:
            return {"state": "rejected", "note": invalid}
        servers = [str(s) for s in servers]
        if not user_approved:
            return {"state": CONFIRMATION_REQUIRED,
                    "note": "cambiar los DNS afecta a la resolución de todo el sistema: "
                            "requiere confirmación explícita",
                    "action": {"iface": iface, "servers": servers}}
        rc_path = self.resolvectl_path()
        pk = self.pkexec_path()
        if not rc_path or not pk:
            return {"state": UNAVAILABLE,
                    "note": "se requiere resolvectl (systemd) y pkexec (polkit)"}
        previous = self.current()
        prev_servers = previous.get("servers", []) if previous.get("state") == "ok" else []
        argv = [pk, rc_path, "dns", iface] + servers
        try:
            proc = self._runner(argv, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "error", "note": f"no se pudo aplicar el DNS: {type(exc).__name__}"}
        if proc.returncode != 0:
            return {"state": "error",
                    "note": "resolvectl terminó con código " + str(proc.returncode) + ": "
                            + (proc.stderr or "").strip()}
        self._seq += 1
        mod: Dict[str, Any] = {
            "id": f"ngne-dns-{self._seq}", "type": "dns", "iface": iface,
            "servers": servers, "previous_servers": prev_servers,
            "time": self._clock(),
        }
        verified = self._verify(iface, servers)
        if verified.get("state") == "ok":
            mod["state"] = "applied"
            self._history.append(mod)
            return {"state": "ok", "modification": dict(mod), "verified": True}
        restore = self._restore_mod(mod)
        return {"state": "error",
                "note": "el DNS no quedó verificado tras aplicar; se restauró el estado previo",
                "restore": restore}

    def _verify(self, iface: str, expected: List[str]) -> Dict[str, Any]:
        rc_path = self.resolvectl_path()
        if not rc_path:
            return {"state": UNAVAILABLE, "note": "sin resolvectl no se puede verificar"}
        try:
            proc = self._runner([rc_path, "dns", iface], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "error", "note": f"verificación fallida: {type(exc).__name__}"}
        found = set()
        for token in (proc.stdout or "").replace("(", " ").replace(")", " ") \
                .replace(":", " ").split():
            try:
                ipaddress.ip_address(token)
                found.add(token)
            except ValueError:
                continue
        missing = [s for s in expected if s not in found]
        if missing:
            return {"state": "error", "note": "servidores no visibles en el enlace: "
                    + ", ".join(missing)}
        return {"state": "ok"}

    def _restore_mod(self, mod: Dict[str, Any]) -> Dict[str, Any]:
        rc_path = self.resolvectl_path()
        pk = self.pkexec_path()
        if not rc_path or not pk:
            return {"state": UNAVAILABLE, "note": "sin resolvectl o sin pkexec: no se puede restaurar"}
        iface = mod["iface"]
        prev = list(mod.get("previous_servers") or [])
        if prev:
            argv = [pk, rc_path, "dns", iface] + prev
        else:
            argv = [pk, rc_path, "revert", iface]
        try:
            proc = self._runner(argv, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "error", "note": f"restauración fallida: {type(exc).__name__}"}
        if proc.returncode != 0:
            return {"state": "error",
                    "note": "restauración fallida, código " + str(proc.returncode)}
        expected = prev if prev else []
        if expected:
            verified = self._verify(iface, expected)
            if verified.get("state") != "ok":
                return {"state": "error", "note": "la restauración no se pudo verificar"}
        mod["state"] = "reverted"
        return {"state": "ok", "verified": True}

    def undo_last(self) -> Dict[str, Any]:
        applied = [m for m in self._history if m.get("state") == "applied"]
        if not applied:
            return {"state": UNAVAILABLE, "note": "no hay cambios de DNS que deshacer"}
        mod = applied[-1]
        result = self._restore_mod(mod)
        return {"state": result["state"], "modification": dict(mod), "restore": result}

    def modifications(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in self._history]
