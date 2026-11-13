"""Motor del Gaming Network Engine (NGNE).

Integra diagnóstico, perfiles y optimizador sin duplicar sistemas:
  - El diagnóstico es de solo lectura; nada cambia sin consentimiento.
  - set_profile() adapta el perfil elegido al contexto real (tipo de enlace,
    nivel de hardware, colas disponibles) con profiles.adapt_profile.
  - optimize() aplica lo que el perfil declara: la cola con QueueOptimizer
    (requiere user_approved=True) y, solo si el usuario pasa servidores DNS,
    el cambio de DNS con DnsOptimizer (también con consentimiento). NGNE
    nunca elige servidores DNS por su cuenta.
  - undo_last() deshace la última modificación (cola o DNS, la más reciente)
    con verificación de la restauración.
  - network_overview(): lectura ligera sin ping, para refresco periódico.
  - diagnose(): diagnóstico completo con medición de latencia, bajo demanda.
  - health_check(): chequeo simple para el watchdog (integración fase 5).
  - No promete mejoras de ping: aplica colas y DNS verificados y medidos.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

from nexora.gaming.network.diagnostics import NetworkDiagnostics, UNAVAILABLE
from nexora.gaming.network.optimizer import DnsOptimizer, QueueOptimizer
from nexora.gaming.network.profiles import adapt_profile


class GamingNetworkEngine:
    """Fachada de NGNE: diagnóstico, perfiles adaptados y optimización."""

    def __init__(
        self,
        diagnostics: Optional[NetworkDiagnostics] = None,
        optimizer: Optional[QueueOptimizer] = None,
        dns: Optional[DnsOptimizer] = None,
        clock: Callable[[], float] = time.monotonic,
        history_size: int = 100,
    ):
        self.diagnostics = diagnostics or NetworkDiagnostics()
        self.optimizer = optimizer or QueueOptimizer(clock=clock)
        self.dns = dns or DnsOptimizer(clock=clock)
        self._clock = clock
        self._profile_name: Optional[str] = None
        self._profile_effective: Optional[Dict[str, Any]] = None
        self._adaptations: List[str] = []
        self._history: deque = deque(maxlen=history_size)

    # -- contexto y perfil -----------------------------------------------------
    def primary_iface(self) -> Optional[str]:
        """Interfaz principal: la de la ruta por defecto o la primera activa."""
        gw = self.diagnostics.gateway()
        if gw.get("state") == "ok":
            return gw.get("iface")
        inv = self.diagnostics.interfaces()
        for i in inv.get("interfaces", []):
            if i.get("operstate") == "up" and i.get("type") in ("ethernet", "wireless"):
                return i["name"]
        return None

    def context(self) -> Dict[str, Any]:
        """Contexto real para adaptar perfiles: enlace y nivel de hardware."""
        link = "unknown"
        primary = self.primary_iface()
        inv = self.diagnostics.interfaces()
        for i in inv.get("interfaces", []):
            if i.get("name") == primary:
                kind = i.get("type")
                link = "wifi" if kind == "wireless" else ("ethernet" if kind == "ethernet" else "unknown")
        tier = None
        try:
            from nexora.core.profiles import detect_hardware, suggest_tier
            hw = detect_hardware()
            if hw is not None:
                tier = suggest_tier(hw.cpu_cores, hw.ram_gb)
        except Exception:
            tier = None
        if tier is None:
            tier = "balanced"  # contexto neutro, declarado como tal
        return {"link_type": link, "hardware_tier": tier}

    def set_profile(self, name: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fija el perfil de juego adaptado al contexto (no toca el sistema)."""
        ctx = self.context()
        ctx.update(context or {})
        adapted = adapt_profile(name, ctx)
        self._profile_name = name
        self._profile_effective = adapted["effective"]
        self._adaptations = adapted["adaptations"]
        self._history.append({"time": self._clock(), "event": "profile_set",
                              "profile": name})
        return self.profile()

    def profile(self) -> Dict[str, Any]:
        if self._profile_name is None:
            return {"state": UNAVAILABLE, "note": "sin perfil de juego seleccionado"}
        return {"state": "ok", "name": self._profile_name,
                "effective": self._profile_effective,
                "adaptations": list(self._adaptations)}

    # -- observación -------------------------------------------------------------
    def network_overview(self) -> Dict[str, Any]:
        """Lectura ligera (sin ping ni tc): para refresco periódico del panel."""
        return {
            "interfaces": self.diagnostics.interfaces(),
            "gateway": self.diagnostics.gateway(),
            "dns": self.diagnostics.dns_servers(),
        }

    def diagnose(self) -> Dict[str, Any]:
        """Diagnóstico completo con medición de latencia (bajo demanda)."""
        iface = self.primary_iface()
        capabilities = (self.optimizer.compatibility(iface) if iface
                        else {"state": UNAVAILABLE, "note": "sin interfaz principal detectada"})
        return {
            "diagnostics": self.diagnostics.summary(),
            "profile": self.profile(),
            "capabilities": capabilities,
        }

    # -- aplicación ----------------------------------------------------------------
    def optimize(self, user_approved: bool = False,
                 dns_servers: Optional[List[str]] = None) -> Dict[str, Any]:
        """Aplica lo declarado por el perfil. La cola y el DNS exigen aprobación."""
        prof = self.profile()
        if prof.get("state") != "ok":
            return {"state": UNAVAILABLE,
                    "note": "selecciona un perfil de juego antes de optimizar"}
        iface = self.primary_iface()
        if iface is None:
            return {"state": UNAVAILABLE, "note": "sin interfaz principal detectada"}
        eff = prof["effective"]
        results: Dict[str, Any] = {}
        if eff.get("qdisc"):
            results["qdisc"] = self.optimizer.apply_qdisc(
                iface, eff["qdisc"], params=eff.get("qdisc_params") or {},
                user_approved=user_approved)
        else:
            results["qdisc"] = {"state": "skipped",
                                "note": "el perfil no declara una cola que aplicar"}
        if dns_servers:
            results["dns"] = self.dns.set_servers(iface, dns_servers,
                                                  user_approved=user_approved)
        else:
            results["dns"] = {"state": "skipped",
                              "note": "sin cambio de DNS: NGNE no elige servidores por su cuenta"}
        ok = all(r.get("state") in ("ok", "skipped") for r in results.values())
        self._history.append({
            "time": self._clock(), "event": "optimize",
            "results": {k: v.get("state") for k, v in results.items()},
        })
        return {"state": "ok" if ok else "error", "results": results}

    def undo_last(self) -> Dict[str, Any]:
        """Deshace la modificación más reciente entre cola y DNS, verificada."""
        candidates: List[Any] = []
        candidates += [("qdisc", m) for m in self.optimizer.modifications()
                       if m.get("state") == "applied"]
        candidates += [("dns", m) for m in self.dns.modifications()
                       if m.get("state") == "applied"]
        if not candidates:
            return {"state": UNAVAILABLE, "note": "no hay modificaciones que deshacer"}
        kind, _mod = max(candidates, key=lambda kv: kv[1].get("time", 0))
        if kind == "qdisc":
            result = self.optimizer.undo_last()
        else:
            result = self.dns.undo_last()
        self._history.append({"time": self._clock(), "event": "undo",
                              "kind": kind, "result": result.get("state")})
        return result

    # -- estado y salud --------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "profile": self.profile(),
            "qdisc_modifications": self.optimizer.modifications(),
            "dns_modifications": self.dns.modifications(),
            "history": list(self._history),
        }

    def health_check(self) -> bool:
        """Chequeo simple para el watchdog: el inventario de red es legible."""
        try:
            inv = self.diagnostics.interfaces()
            return inv.get("state") == "ok" and len(inv.get("interfaces", [])) > 0
        except Exception:
            return False
