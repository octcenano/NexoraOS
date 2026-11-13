"""Supervision ligera de componentes (watchdog del core).

Diseño:
  - No es un demonio residente por defecto: 'run_once' hace una pasada y sale.
    El modo bucle ('--loop') existe para la unidad systemd opcional, y el
    apagado limpio se solicita con 'request_stop()'.
  - Nunca modifica configuración ni políticas: solo comprueba estado y ejecuta
    la función de recuperación registrada por el propio componente.
  - Verificación del resultado: tras una recuperación que se declara exitosa se
    vuelve a comprobar la salud real del componente; si no se recupera de
    verdad, el intento cuenta como fallo (nunca se simula éxito).
  - Reinicios acotados y backoff progresivo: la espera entre reintentos parte
    del cooldown base y crece exponencialmente (acotada por 'backoff_max_s')
    a partir del segundo reintento completado.
  - Circuit breaker por componente: tras 'max_restarts' fallos consecutivos
    de recuperación el circuito se abre (sin reintentos); tras
    'circuit_reset_s' pasa a semiabierto y se permite una única prueba; si
    la prueba verifica la salud, el circuito se cierra y los contadores se
    reinician; si falla, se reabre. La entrada de registro marca con 'probe'
    los intentos que se ejecutaron como prueba semiabierta.
  - Historial de incidencias acotado (transiciones sano->degradado) y registro
    detallado de cada intento (duración, verificación, estado del circuito).
  - 'diagnose()': informe de diagnóstico sin ejecutar recuperaciones.
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
        backoff_factor: float = 2.0,
        backoff_max_s: float = 300.0,
        circuit_reset_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if max_restarts < 0:
            raise ValueError("max_restarts no puede ser negativo")
        if backoff_factor < 1.0:
            raise ValueError("backoff_factor no puede ser menor que 1.0")
        if cooldown_s < 0 or backoff_max_s < 0 or circuit_reset_s <= 0:
            raise ValueError("los tiempos del watchdog deben ser no negativos")
        self.max_restarts = max_restarts
        self.cooldown_s = cooldown_s
        self.backoff_factor = backoff_factor
        self.backoff_max_s = backoff_max_s
        self.circuit_reset_s = circuit_reset_s
        self._clock = clock
        self._sleep = sleeper
        self._components: Dict[str, Component] = {}
        self._restarts: Dict[str, int] = {}
        self._consecutive_failures: Dict[str, int] = {}
        self._last_attempt: Dict[str, float] = {}
        self._was_healthy: Dict[str, bool] = {}
        self._circuit: Dict[str, str] = {}
        self._circuit_opened_at: Dict[str, float] = {}
        self._exhausted: set = set()
        self._log: deque = deque(maxlen=log_size)
        self._incidents: deque = deque(maxlen=incidents_size)
        self._stop_requested = False

    # -- registro ----------------------------------------------------------
    def register(self, component: Component) -> None:
        if component.name in self._components:
            raise ValueError(f"Componente duplicado: {component.name}")
        self._components[component.name] = component
        self._restarts[component.name] = 0

    # -- apagado limpio ------------------------------------------------------
    def request_stop(self) -> None:
        """Solicita el apagado limpio del bucle de supervisión."""
        self._stop_requested = True

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    # -- backoff y circuit breaker -------------------------------------------
    def _backoff_for(self, name: str) -> float:
        """Espera antes del siguiente intento: cooldown base y, a partir del
        segundo reintento completado, crecimiento exponencial acotado."""
        done = self._restarts.get(name, 0)
        if done <= 1:
            return self.cooldown_s
        return min(self.cooldown_s * (self.backoff_factor ** (done - 1)), self.backoff_max_s)

    def circuit_states(self) -> Dict[str, str]:
        return {name: self._circuit.get(name, "closed") for name in self._components}

    # -- supervisión -------------------------------------------------------
    def check(self, name: str, allow_recover: bool = True) -> Dict[str, Any]:
        comp = self._components.get(name)
        if comp is None:
            raise KeyError(f"Componente desconocido: {name}")
        now = self._clock()
        entry: Dict[str, Any] = {
            "time": now, "component": name,
            "circuit": self._circuit.get(name, "closed"),
        }
        try:
            healthy = bool(comp.health_check())
        except Exception as exc:  # una comprobación defectuosa no derriba el watchdog
            healthy = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["healthy"] = healthy

        if healthy:
            if self._circuit.get(name, "closed") != "closed":
                self._circuit[name] = "closed"
                self._exhausted.discard(name)
                self._consecutive_failures[name] = 0
                entry["circuit"] = "closed"
                entry["circuit_rearmed"] = True
            self._was_healthy[name] = True
            self._log.append(entry)
            return entry

        entry["restarted"] = False
        circuit = self._circuit.get(name, "closed")
        if circuit == "open":
            since_open = now - self._circuit_opened_at.get(name, now)
            if allow_recover and comp.recover is not None and since_open >= self.circuit_reset_s:
                self._circuit[name] = "half_open"
                circuit = "half_open"
                entry["circuit"] = "half_open"
            else:
                entry["exhausted"] = True
                if comp.recover is not None:
                    entry["circuit_wait_s"] = round(self.circuit_reset_s - since_open, 3)
        entry["exhausted"] = entry.get("exhausted", circuit == "open")

        if allow_recover and comp.recover is not None and circuit in ("closed", "half_open"):
            attempts = self._restarts.get(name, 0)
            wait = self._backoff_for(name)
            since = now - self._last_attempt.get(name, 0.0)
            probe = circuit == "half_open"
            if probe or (attempts < self.max_restarts and since >= wait):
                if probe:
                    entry["probe"] = True
                self._last_attempt[name] = now
                self._restarts[name] = attempts + 1
                t0 = self._clock()
                try:
                    recovered = bool(comp.recover())
                except Exception as exc:
                    recovered = False
                    entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["restarted"] = True
                entry["recovery_ms"] = round((self._clock() - t0) * 1000.0, 2)
                verified = False
                if recovered:
                    # verificación del resultado: la salud real tras recuperar
                    try:
                        verified = bool(comp.health_check())
                    except Exception as exc:
                        verified = False
                        entry["verify_error"] = f"{type(exc).__name__}: {exc}"
                entry["recovered"] = recovered
                entry["verified"] = verified
                entry["restart_count"] = self._restarts[name]
                if recovered and verified:
                    self._consecutive_failures[name] = 0
                    self._circuit[name] = "closed"
                    self._exhausted.discard(name)
                    entry["circuit"] = "closed"
                else:
                    self._consecutive_failures[name] = self._consecutive_failures.get(name, 0) + 1
                    if self._consecutive_failures[name] >= self.max_restarts:
                        self._circuit[name] = "open"
                        self._circuit_opened_at[name] = self._clock()
                        self._exhausted.add(name)
                        entry["circuit"] = "open"
                        entry["exhausted"] = True
            elif attempts >= self.max_restarts and circuit == "closed":
                self._circuit[name] = "open"
                self._circuit_opened_at[name] = now
                self._exhausted.add(name)
                entry["circuit"] = "open"
                entry["exhausted"] = True
            else:
                entry["backoff_remaining_s"] = round(wait - since, 3)

        # historial de incidencias: transición sano -> no sano
        if self._was_healthy.get(name, True):
            self._incidents.append({
                "time": entry["time"], "component": name,
                "error": entry.get("error", "comprobación fallida"),
            })
        self._was_healthy[name] = False
        self._log.append(entry)
        return entry

    def check_all(self) -> List[Dict[str, Any]]:
        return [self.check(name) for name in self._components]

    @staticmethod
    def _overall(results: List[Dict[str, Any]]) -> str:
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
        return "ok" if all(s == "ok" for s in states) else "failed" if "failed" in states else "degraded"

    def run_once(self) -> Dict[str, Any]:
        results = self.check_all()
        return {"overall": self._overall(results), "components": results}

    # -- bucle de supervisión con apagado limpio ------------------------------
    def run_loop(
        self,
        interval_s: float,
        on_pass: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[int, Exception], None]] = None,
        max_errors: int = 3,
    ) -> int:
        """Bucle de supervisión pensado para systemd.

        Termina con 0 en apagado limpio (request_stop) y con 3 si supera
        max_errors pasadas consecutivas con error interno.
        """
        consecutive = 0
        while not self._stop_requested:
            try:
                report = self.run_once()
                consecutive = 0
                if on_pass is not None:
                    on_pass(report)
            except Exception as exc:
                consecutive += 1
                if on_error is not None:
                    on_error(consecutive, exc)
                if consecutive >= max(max_errors, 1):
                    self._log.append({"time": self._clock(), "event": "watchdog_abort_errors"})
                    return 3
            self._sleep(max(interval_s, 1.0))
        self._log.append({"time": self._clock(), "event": "watchdog_stop_clean"})
        return 0

    # -- diagnóstico (sin efectos) ------------------------------------------
    def diagnose(self) -> Dict[str, Any]:
        """Informe de diagnóstico: estado actual, reinicios e incidencias.

        No ejecuta recuperaciones ni modifica nada: solo observa.
        """
        results = [self.check(name, allow_recover=False) for name in self._components]
        recommendations: List[str] = []
        for r in results:
            if r.get("exhausted"):
                recommendations.append(
                    f"'{r['component']}' agotó sus {self.max_restarts} recuperaciones "
                    "consecutivas: circuito abierto; revisa sus logs; se permitirá una "
                    f"prueba de recuperación dentro de {self.circuit_reset_s} s."
                )
            elif not r["healthy"]:
                recommendations.append(
                    f"'{r['component']}' está degradado; ejecuta 'nexora health' para el detalle."
                )
        return {
            "overall": self._overall(results),
            "components": results,
            "incidents": list(self._incidents),
            "restart_counts": dict(self._restarts),
            "circuits": self.circuit_states(),
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

    def check_nke() -> bool:
        """NKE: sus capacidades se pueden leer y son un dict válido."""
        try:
            from nexora.nke.capabilities import detect_capabilities
            caps = detect_capabilities()
            return isinstance(caps, dict) and isinstance(caps.get("kernel_release"), str)
        except Exception:
            return False

    wd.register(Component("config", check_config, description="Carga y validación de configuración"))
    wd.register(Component("agent_isolation", check_isolation, description="Memoria privada por modo"))
    wd.register(Component("vault", check_vault, description="Backend de secretos disponible"))
    wd.register(Component("nke", check_nke, description="Nexora Kernel Engine: lectura de capacidades del kernel"))
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
    def on_pass(report: Dict[str, Any]) -> None:
        if report["overall"] != "ok":
            for r in report["components"]:
                if not r["healthy"]:
                    print(f"[watchdog] componente degradado: {r['component']}", file=sys.stderr)

    def on_error(count: int, exc: Exception) -> None:
        print(f"[watchdog] error interno ({count}/{args.max_loop_errors}): {exc}", file=sys.stderr)

    return wd.run_loop(args.loop, on_pass=on_pass, on_error=on_error,
                       max_errors=args.max_loop_errors)


if __name__ == "__main__":
    raise SystemExit(main())
