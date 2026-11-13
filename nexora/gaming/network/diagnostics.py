"""Diagnóstico de red para el modo Gaming (NGNE).

Diseño:
  - Solo lectura: este módulo nunca modifica la configuración de red.
  - Datos reales de /sys/class/net, /proc/net/route, /proc/net/wireless y
    /etc/resolv.conf. Donde el sistema no ofrece el dato, el campo se marca
    como no disponible (available=False y una nota); nunca se inventa.
  - Latencia con ping contra objetivos explícitos: la puerta de enlace
    (red local) por defecto. No se contacta con servidores externos salvo
    que el usuario pase el objetivo (servidor de juego o sonda de Internet
    elegida por él).
  - jitter_ms se aproxima con la desviación media (mdev) que reporta ping;
    es una aproximación documentada, no una medición RFC 3550.
  - El ejecutor de subprocess es inyectable para probar sin red real.
  - Bufferbloat: la medición bajo carga no está implementada en la beta; se
    declara como no disponible en lugar de simularla.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Callable, Dict, Optional

Runner = Callable[..., subprocess.CompletedProcess]

UNAVAILABLE = "unavailable"


def _read_text(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _read_int(path: str) -> Optional[int]:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def _hex_to_ip(hex_value: str) -> Optional[str]:
    try:
        raw = bytes.fromhex(hex_value)
    except ValueError:
        return None
    if len(raw) != 4:
        return None
    return ".".join(str(b) for b in reversed(raw))


class NetworkDiagnostics:
    """Diagnóstico de red de solo lectura con datos reales del sistema."""

    def __init__(
        self,
        sys_net: str = "/sys/class/net",
        route_path: str = "/proc/net/route",
        wireless_path: str = "/proc/net/wireless",
        resolv_path: str = "/etc/resolv.conf",
        runner: Optional[Runner] = None,
        ping_path: Optional[str] = None,
        iw_path: Optional[str] = None,
        ping_count: int = 10,
        ping_interval_s: float = 0.2,
        ping_timeout_s: float = 15.0,
    ):
        if ping_count < 1:
            raise ValueError("ping_count debe ser al menos 1")
        if ping_interval_s <= 0 or ping_timeout_s <= 0:
            raise ValueError("los tiempos de ping deben ser positivos")
        self.sys_net = sys_net
        self.route_path = route_path
        self.wireless_path = wireless_path
        self.resolv_path = resolv_path
        self._runner: Runner = runner or subprocess.run
        self._ping_path = ping_path
        self._iw_path = iw_path
        self.ping_count = ping_count
        self.ping_interval_s = ping_interval_s
        self.ping_timeout_s = ping_timeout_s

    # -- interfaces ----------------------------------------------------------
    def _wireless_levels(self) -> Dict[str, float]:
        """Nivel de señal (dBm) por interfaz desde /proc/net/wireless."""
        text = _read_text(self.wireless_path)
        levels: Dict[str, float] = {}
        if not text:
            return levels
        for line in text.splitlines():
            if ":" not in line:
                continue
            name, rest = line.split(":", 1)
            name = name.strip()
            fields = rest.split()
            if len(fields) < 3:
                continue
            try:
                float(fields[0])  # campo de estado numérico: descarta cabeceras
                level = float(fields[2])
            except ValueError:
                continue
            levels[name] = level
        return levels

    def _band(self, name: str) -> Dict[str, Any]:
        """Banda Wi-Fi vía iw (solo si se configura iw_path). Sin iw: no disponible."""
        if not self._iw_path:
            return {"available": False, "note": "requiere iw (no configurado); no se deduce sin él"}
        if not os.path.exists(self._iw_path):
            return {"available": False, "note": "iw no está instalado en este sistema"}
        try:
            proc = self._runner([self._iw_path, "dev", name, "link"],
                                capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"available": False, "note": f"iw falló: {type(exc).__name__}"}
        freq = None
        signal = None
        for line in (proc.stdout or "").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == "freq:":
                try:
                    freq = float(parts[1])
                except ValueError:
                    pass
            if len(parts) >= 2 and parts[0] == "signal:":
                try:
                    signal = float(parts[1])
                except ValueError:
                    pass
        if freq is None:
            return {"available": False, "note": "iw no devolvió frecuencia (¿sin conexión?)"}
        if freq >= 5000:
            band = "5 GHz"
        elif freq >= 2400:
            band = "2.4 GHz"
        else:
            band = f"{freq} MHz"
        return {"available": True, "band": band, "freq_mhz": freq, "signal_dbm_iw": signal}

    def interfaces(self) -> Dict[str, Any]:
        """Inventario de interfaces con datos reales de /sys/class/net."""
        try:
            names = sorted(os.listdir(self.sys_net))
        except OSError as exc:
            return {"state": UNAVAILABLE,
                    "note": f"no se pudo leer {self.sys_net}: {type(exc).__name__}",
                    "interfaces": []}
        levels = self._wireless_levels()
        out = []
        for name in names:
            base = os.path.join(self.sys_net, name)
            is_wireless = os.path.isdir(os.path.join(base, "wireless")) or name in levels
            has_carrier = os.path.exists(os.path.join(base, "carrier"))
            kind = "wireless" if is_wireless else ("ethernet" if has_carrier else "unknown")
            entry: Dict[str, Any] = {
                "name": name,
                "type": kind,
                "operstate": _read_text(os.path.join(base, "operstate")),
                "mtu": _read_int(os.path.join(base, "mtu")),
            }
            if entry["operstate"] is not None:
                entry["operstate"] = entry["operstate"].strip()
            if kind == "ethernet":
                entry["carrier"] = _read_int(os.path.join(base, "carrier"))
                entry["speed_mbps"] = _read_int(os.path.join(base, "speed"))
                entry["duplex"] = _read_text(os.path.join(base, "duplex"))
                if entry["duplex"] is not None:
                    entry["duplex"] = entry["duplex"].strip()
                if entry["speed_mbps"] is None:
                    entry["speed_note"] = "no disponible (interfaz caída o el driver no la publica)"
            if kind == "wireless":
                entry["signal_dbm"] = levels.get(name)
                entry["band"] = self._band(name)
            stats: Dict[str, Any] = {}
            for stat in ("rx_errors", "tx_errors", "rx_dropped", "tx_dropped"):
                stats[stat] = _read_int(os.path.join(base, "statistics", stat))
            entry["statistics"] = stats
            out.append(entry)
        return {"state": "ok", "interfaces": out}

    # -- rutas y DNS -----------------------------------------------------------
    def gateway(self) -> Dict[str, Any]:
        """Puerta de enlace por defecto desde /proc/net/route (solo lectura)."""
        text = _read_text(self.route_path)
        if text is None:
            return {"state": UNAVAILABLE, "note": "no se pudo leer " + self.route_path}
        for line in text.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue
            iface, dest, gw_hex = parts[0], parts[1], parts[2]
            if dest == "00000000" and gw_hex != "00000000":
                ip = _hex_to_ip(gw_hex)
                if ip:
                    return {"state": "ok", "ip": ip, "iface": iface}
        return {"state": UNAVAILABLE, "note": "sin ruta por defecto con puerta de enlace"}

    def dns_servers(self) -> Dict[str, Any]:
        """Servidores DNS declarados en resolv.conf (solo lectura)."""
        text = _read_text(self.resolv_path)
        if text is None:
            return {"state": UNAVAILABLE, "note": "no se pudo leer " + self.resolv_path,
                    "servers": []}
        servers = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("nameserver"):
                parts = line.split()
                if len(parts) >= 2:
                    servers.append(parts[1])
            if len(servers) >= 8:
                break
        if not servers:
            return {"state": UNAVAILABLE, "note": "sin servidores DNS declarados", "servers": []}
        return {"state": "ok", "servers": servers, "source": self.resolv_path}

    # -- latencia ----------------------------------------------------------------
    def ping(self, target: str, count: Optional[int] = None) -> Dict[str, Any]:
        """Mide latencia, pérdida y jitter aproximado contra un objetivo explícito."""
        if not target or not str(target).strip():
            return {"state": UNAVAILABLE, "note": "sin objetivo: pásalo explícitamente"}
        target = str(target).strip()
        ping = self._ping_path or shutil.which("ping")
        if not ping or not os.path.exists(ping):
            return {"state": UNAVAILABLE, "note": "ping no está disponible en este sistema",
                    "target": target}
        n = count or self.ping_count
        argv = [ping, "-c", str(n), "-i", str(self.ping_interval_s),
                "-w", str(self.ping_timeout_s), target]
        try:
            proc = self._runner(argv, capture_output=True, text=True,
                                timeout=self.ping_timeout_s + 5)
        except subprocess.TimeoutExpired:
            return {"state": "error", "target": target, "loss_pct": None,
                    "note": "ping agotó el tiempo de espera"}
        except OSError as exc:
            return {"state": "error", "target": target, "loss_pct": None,
                    "note": f"no se pudo ejecutar ping: {type(exc).__name__}"}
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        loss = None
        rtt = None
        for line in out.splitlines():
            if "packet loss" in line:
                for token in line.replace(",", " ").split():
                    if token.endswith("%"):
                        try:
                            loss = float(token[:-1])
                        except ValueError:
                            pass
            if "min/avg/max" in line and "=" in line:
                values = line.split("=", 1)[1].split()
                if len(values) >= 4:
                    try:
                        rtt = [float(v) for v in values[:4]]
                    except ValueError:
                        rtt = None
        entry: Dict[str, Any] = {
            "target": target, "packets_sent": n, "loss_pct": loss,
            "returncode": proc.returncode,
            "jitter_note": "jitter aproximado con la desviación media (mdev) de ping",
        }
        if rtt:
            entry.update({"min_ms": rtt[0], "avg_ms": rtt[1], "max_ms": rtt[2],
                          "jitter_ms": rtt[3]})
        else:
            entry.update({"min_ms": None, "avg_ms": None, "max_ms": None,
                          "jitter_ms": None,
                          "note": "sin estadísticas rtt: sin respuestas o ping no compatible"})
        if loss is None:
            entry["state"] = "error"
            entry["note"] = "salida de ping no interpretable"
        elif loss >= 100.0:
            entry["state"] = "error"
        elif loss > 0.0:
            entry["state"] = "degraded"
        else:
            entry["state"] = "ok"
        return entry

    def latency_report(self, internet_target: Optional[str] = None,
                       game_server: Optional[str] = None) -> Dict[str, Any]:
        """Latencia local (puerta de enlace) y, solo si el usuario la pide,
        contra un objetivo de Internet o de servidor de juego."""
        gw = self.gateway()
        if gw.get("state") == "ok":
            local = self.ping(gw["ip"])
        else:
            local = {"state": UNAVAILABLE,
                     "note": "sin puerta de enlace: " + gw.get("note", "")}
        if internet_target:
            internet = self.ping(internet_target)
        else:
            internet = {"state": UNAVAILABLE,
                        "note": "sin objetivo de Internet: indícalo explícitamente; "
                                "NGNE no elige servidores por su cuenta"}
        if game_server:
            game = self.ping(game_server)
        else:
            game = {"state": UNAVAILABLE,
                    "note": "sin servidor de juego: indícalo (host o IP); "
                            "el puerto no participa en ping"}
        return {"local": local, "internet": internet, "game_server": game,
                "note": "las cifras son mediciones puntuales; no se promete mejora de ping"}

    # -- resumen -----------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        """Instantánea completa de diagnóstico (solo lectura) para panel y CLI."""
        return {
            "interfaces": self.interfaces(),
            "gateway": self.gateway(),
            "dns": self.dns_servers(),
            "latency": self.latency_report(),
            "bufferbloat": {"state": UNAVAILABLE,
                            "note": "medición bajo carga no implementada en la beta; no se simula"},
            "scope": "readonly_diagnostics",
        }
