"""Supervisión ligera de componentes (watchdog del core).

Diseño:
  - No es un demonio residente por defecto: ``run_once`` hace una pasada y sale.
    El modo bucle (``--loop``) existe para la unidad systemd opcional.
  - Nunca modifica configuración ni políticas: solo comprueba estado y ejecuta
    la función de recuperación registrada por el propio componente.
  - Reinicios acotados: un componente que falla más de ``max_restarts`` veces
    se marca ``exhausted`` y no se reintenta hasta reinicio manual del watchdog.
  - Historial de incidencias acotado (transiciones sano->degradado).
  - ``diagnose()``: informe de diagnóstico sin ejecutar recuperaciones.
  - En modo bucle, un error del propio watchdog se registra y no derriba el
    proceso; si falla N pasadas consecutivas, sale (systemd lo reinicia con
    sus propios límites). Nunca escribe archivos ni cambia políticas.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional


class Component:
    """Componente supervisable: comprobación de salud y recuperación opcional."""

    def __init__(
        self,
        name: str,
        health_check: Callable[[], bool],
        recover: Optional[Callable[[], bool]] = None,
        description: str = "",
    ):
        if not name or not callable(health_check):
            raise ValueError("Component necesita name y health_check")
        self.name = name
        self.health_check = health_check
        self.recover = recover
        self.description = description


class Watchdog:
    def __init__(
        self,
        max_restarts: int = 3,
        cooldown_s: float = 5.0,
        log_size: int = 200,
        incidents_size: int = 50,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if max_restarts < 0:
            raise ValueError("max_restarts no puede ser negativo")
        self.max_restarts = max_restarts
        self.cooldown_s = cooldown_s
        self._clock = clock
        self._sleep = sleeper
        self._components: Dict[str, Component] = {}
        self._restarts: Dict[str, int] = {}
        self._last_attempt: Dict[str, float] = {}
        self._was_healthy: Dict[str, bool] = {}
        self._exhausted: set = set()
        self._log: deque = deque(maxlen=log_size)
        self._incidents: deque = deque(maxlen=incidents_size)

    # -- registro ----------------------------------------------------------
    def register(self, component: Component) -> None:
        if component.name in self._components:
            raise ValueError(f"Componente duplicado: {component.name}")
        self._components[component.name] = component
        self._restarts[component.name] = 0

    # -- supervisión -------------------------------------------------------
    def check(self, name: str) -> Dict[str, Any]:
        comp = self._components.get(name)
        if comp is None:
            raise KeyError(f"Componente desconocido: {name}")
        entry: Dict[str, Any] = {"time": self._clock(), "component": name}
        try:
            healthy = bool(comp.health_check())
        except Exception as exc:  # una comprobación defectuosa no derriba el watchdog
            healthy = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["healthy"] = healthy
        if not healthy and name not in self._exhausted:
            entry["restarted"] = False
            entry["exhausted"] = False
            if comp.recover is not None and self._restarts[name] < self.max_restarts:
                now = self._clock()
                since = now - self._last_attempt.get(name, 0.0)
                if since >= self.cooldown_s:
                    self._last_attempt[name] = now
                    self._restarts[name] += 1
                    try:
                        recovered = bool(comp.recover())
                    except Exception as exc:
                        recovered = False
                        entry["error"] = f"{type(exc).__name__}: {exc}"
                    entry["restarted"] = True
                    entry["recovered"] = recovered
                    entry["restart_count"] = self._restarts[name]
            elif comp.recover is not None:
                self._exhausted.add(name)
                entry["exhausted"] = True
        # historial de incidencias: transición sano -> no sano
        if not healthy and self._was_healthy.get(name, True):
            self._incidents.append({
                "time": entry["time"], "component": name,
                "error": entry.get("error", "comprobación fallida"),
            })
        self._was_healthy[name] = healthy
        self._log.append(entry)
        return entry

    def check_all(self) -> List[Dict[str, Any]]:
        return [self.check(name) for name in self._components]

    def run_once(self) -> Dict[str, Any]:
        results = self.check_all()
        states = []
        for r in results:
            if r["healthy"]:
                states.append("ok")
            elif r.get("restarted") and r.get("recovered"):
                states.append("ok")
            elif r.get("exhausted"):
                states.append("failed")
            else:
                states.append("degraded")
        overall = "ok" if all(s == "ok" for s in states) else "failed" if "failed" in states else "degraded"
        return {"overall": overall, "components": results}

    # -- diagnóstico (sin efectos) ------------------------------------------
    def diagnose(self) -> Dict[str, Any]:
        """Informe de diagnóstico: estado actual, reinicios e incidencias.

        No ejecuta recuperaciones ni modifica nada: solo observa.
        """
        report = self.run_once()
        recommendations: List[str] = []
        for r in report["components"]:
            if r.get("exhausted"):
                recommendations.append(
                    f"'{r['component']}' agotó sus {self.max_restarts} recuperaciones: "
                    "revisa sus logs y reinícialo manualmente."
                )
            elif not r["healthy"]:
                recommendations.append(
                    f"'{r['component']}' está degradado; ejecuta 'nexora health' para el detalle."
                )
        return {
            "overall": report["overall"],
            "components": report["components"],
            "incidents": list(self._incidents),
            "restart_counts": dict(self._restarts),
            "recommendations": recommendations,
            "scope": "diagnostic_no_side_effects",
        }

    # -- observación -------------------------------------------------------
    def log_entries(self) -> tuple:
        return tuple(self._log)

    def incidents(self) -> tuple:
        return tuple(self._incidents)

    def restart_count(self, name: str) -> int:
        return self._restarts.get(name, 0)


# -- componentes del core --------------------------------------------------

def watchdog_from_config(cfg: Optional[dict] = None) -> Watchdog:
    """Watchdog con los componentes del core que se pueden comprobar sin red."""
    from nexora.core.config import load_config
    from nexora.core.registry import ModeRegistry
    from nexora.core.vault import vault_from_config, VaultUnavailableError

    wd = Watchdog()

    def check_config() -> bool:
        try:
            return isinstance(load_config(), dict)
        except Exception:
            return False

    def check_isolation() -> bool:
        reg = ModeRegistry()
        modes = reg.names()
        if len(modes) < 2:
            return False
        a, b = reg.create_agent(modes[0]), reg.create_agent(modes[1])
        a.remember("__wd_probe__", 1)
        ok = b.recall("__wd_probe__") is None
        a.forget("__wd_probe__")
        return ok

    def check_vault() -> bool:
        try:
            vault = vault_from_config(cfg or load_config())
            return vault.backend_name in ("memory", "os-keyring")
        except VaultUnavailableError:
            return False

    wd.register(Component("config", check_config, description="Carga y validación de configuración"))
    wd.register(Component("agent_isolation", check_isolation, description="Memoria privada por modo"))
    wd.register(Component("vault", check_vault, description="Backend de secretos disponible"))
    return wd


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="nexora-watchdog", description="Supervisión de componentes NEXORA OS")
    parser.add_argument("--loop", type=float, metavar="SEG", help="Ejecuta en bucle cada SEG segundos (para systemd)")
    parser.add_argument("--diagnose", action="store_true", help="Informe de diagnóstico sin ejecutar recuperaciones")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--max-loop-errors", type=int, default=3,
                        help="Pasadas consecutivas con error interno antes de salir (protección anti-bucle)")
    args = parser.parse_args(argv)

    try:
        wd = watchdog_from_config()
    except Exception as exc:
        print(f"Error al inicializar el watchdog: {exc}", file=sys.stderr)
        return 2

    if args.diagnose:
        report = wd.diagnose()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"Diagnóstico NEXORA OS: {report['overall'].upper()} (sin efectos secundarios)")
            for r in report["components"]:
                print(f"  [{'OK' if r['healthy'] else 'FALLO'}] {r['component']} "
                      f"(reinicios: {report['restart_counts'][r['component']]})")
            for inc in report["incidents"]:
                print(f"  [INCIDENCIA] {inc['component']}: {inc['error']}")
            for rec in report["recommendations"]:
                print(f"  [RECOMENDACIÓN] {rec}")
        return 0 if report["overall"] == "ok" else 1

    if args.loop is None:
        report = wd.run_once()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"Estado general: {report['overall'].upper()}")
            for r in report["components"]:
                extra = ""
                if r.get("restarted"):
                    extra = " (recuperación intentada)"
                if r.get("exhausted"):
                    extra = " (reinicios agotados)"
                print(f"  [{'OK' if r['healthy'] else 'FALLO'}] {r['component']}{extra}")
        return 0 if report["overall"] == "ok" else 1

    # Modo bucle: pensado para ejecutarse bajo systemd. El propio watchdog se
    # protege: un fallo interno no lo mata, pero si falla N pasadas seguidas
    # sale con error para que systemd lo reinicie (con límites propios).
    consecutive_errors = 0
    while True:
        try:
            report = wd.run_once()
            consecutive_errors = 0
            if report["overall"] != "ok":
                for r in report["components"]:
                    if not r["healthy"]:
                        print(f"[watchdog] componente degradado: {r['component']}", file=sys.stderr)
        except Exception as exc:
            consecutive_errors += 1
            print(f"[watchdog] error interno ({consecutive_errors}/{args.max_loop_errors}): {exc}", file=sys.stderr)
            if consecutive_errors >= max(args.max_loop_errors, 1):
                print("[watchdog] saliendo: errores internos consecutivos; systemd aplicará su política de reinicio",
                      file=sys.stderr)
                return 3
        wd._sleep(max(args.loop, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
