"""Tests del watchdog del core (con componentes config, isolation, vault y nke)."""

import unittest
from unittest.mock import patch

import nexora.watchdog as wd


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class ComponentTests(unittest.TestCase):
    def test_component_requiere_nombre_y_check(self):
        with self.assertRaises(ValueError):
            wd.Component("", lambda: True)

    def test_register_duplicado(self):
        clock = FakeClock()
        w = wd.Watchdog(clock=clock, sleeper=lambda s: None)
        w.register(wd.Component("a", lambda: True))
        with self.assertRaises(ValueError):
            w.register(wd.Component("a", lambda: True))


class WatchdogTests(unittest.TestCase):
    def _watchdog(self):
        clock = FakeClock()
        w = wd.Watchdog(max_restarts=2, cooldown_s=5.0, clock=clock, sleeper=lambda s: None)
        return w, clock

    def test_componente_sano(self):
        w, _ = self._watchdog()
        w.register(wd.Component("ok", lambda: True))
        r = w.run_once()
        self.assertEqual(r["overall"], "ok")
        self.assertEqual(r["components"][0]["healthy"], True)

    def test_componente_degradado_sin_recuperacion(self):
        w, _ = self._watchdog()
        w.register(wd.Component("malo", lambda: False))
        r = w.run_once()
        self.assertEqual(r["overall"], "degraded")
        self.assertEqual(r["components"][0].get("restarted"), False)

    def test_excepcion_en_check_no_derriba(self):
        w, _ = self._watchdog()
        def bad():
            raise RuntimeError("boom")
        w.register(wd.Component("bad", bad))
        r = w.run_once()
        self.assertEqual(r["overall"], "degraded")
        self.assertIn("boom", r["components"][0]["error"])

    def test_recuperacion_con_cooldown(self):
        w, clock = self._watchdog()
        # El componente sigue degradado: la recuperación "intenta" pero no cura,
        # de modo que se puede observar el cooldown entre reintentos.
        w.register(wd.Component("svc", lambda: False, recover=lambda: True))
        e1 = w.check("svc")
        self.assertTrue(e1["restarted"])
        self.assertTrue(e1["recovered"])
        # segunda pasada inmediata: cooldown bloquea reintento
        e2 = w.check("svc")
        self.assertFalse(e2["restarted"])
        clock.advance(6.0)
        e3 = w.check("svc")
        self.assertTrue(e3["restarted"])
        self.assertEqual(w.restart_count("svc"), 2)

    def test_limite_de_reinicios_agotado(self):
        w, clock = self._watchdog()
        w.register(wd.Component("muerto", lambda: False, recover=lambda: True))
        for _ in range(6):
            clock.advance(10.0)
            w.check("muerto")
        last = w.check("muerto")
        self.assertTrue(last["exhausted"])
        r = w.run_once()
        self.assertEqual(r["overall"], "failed")

    def test_diagnose_sin_efectos(self):
        w, _ = self._watchdog()
        w.register(wd.Component("malo", lambda: False, recover=lambda: True))
        before = w.restart_count("malo")
        d = w.diagnose()
        self.assertEqual(w.restart_count("malo"), before)  # no recuperó
        self.assertEqual(d["scope"], "diagnostic_no_side_effects")
        self.assertTrue(any("malo" in rec for rec in d["recommendations"]))

    def test_historial_de_incidencias(self):
        w, _ = self._watchdog()
        flips = [True, False, False, True]
        w.register(wd.Component("flip", lambda: flips.pop(0)))
        w.check("flip"); w.check("flip"); w.check("flip"); w.check("flip")
        incs = w.incidents()
        self.assertEqual(len(incs), 1)  # una sola transicion sano->no sano
        self.assertEqual(incs[0]["component"], "flip")


class CircuitBreakerTests(unittest.TestCase):
    def _watchdog(self, **kw):
        clock = FakeClock()
        params = dict(max_restarts=2, cooldown_s=5.0, backoff_factor=2.0,
                      backoff_max_s=300.0, circuit_reset_s=60.0)
        params.update(kw)
        w = wd.Watchdog(clock=clock, sleeper=lambda s: None, **params)
        return w, clock

    def test_recuperacion_verificada_cierra_el_circuito(self):
        """La recuperación se verifica con la salud real del componente."""
        w, _ = self._watchdog()
        state = {"healthy": False}

        def health():
            return state["healthy"]

        def recover():
            state["healthy"] = True
            return True

        w.register(wd.Component("svc", health, recover=recover))
        e = w.check("svc")
        self.assertTrue(e["restarted"])
        self.assertTrue(e["recovered"])
        self.assertTrue(e["verified"])
        self.assertEqual(e["circuit"], "closed")
        self.assertIn("recovery_ms", e)

    def test_recuperacion_sin_verificacion_cuenta_como_fallo(self):
        """recover() devuelve True pero la salud sigue mal: no se da por bueno."""
        w, _ = self._watchdog()
        w.register(wd.Component("svc", lambda: False, recover=lambda: True))
        e = w.check("svc")
        self.assertTrue(e["recovered"])
        self.assertFalse(e["verified"])
        self.assertEqual(e["circuit"], "closed")  # 1 fallo consecutivo < max_restarts

    def test_circuito_se_abre_tras_fallos_consecutivos(self):
        w, clock = self._watchdog()
        w.register(wd.Component("muerto", lambda: False, recover=lambda: True))
        clock.advance(10)
        w.check("muerto")
        clock.advance(10)
        e2 = w.check("muerto")
        self.assertEqual(e2["circuit"], "open")
        clock.advance(10)
        e3 = w.check("muerto")
        self.assertFalse(e3["restarted"])
        self.assertTrue(e3["exhausted"])
        self.assertEqual(w.restart_count("muerto"), 2)

    def test_circuito_semiabierto_permite_una_prueba_y_cierra(self):
        """Tras circuit_reset_s se permite una prueba: si verifica, cierra."""
        w, clock = self._watchdog(circuit_reset_s=30.0)
        state = {"healthy": False, "cure": False}

        def health():
            return state["healthy"]

        def recover():
            if state["cure"]:
                state["healthy"] = True
            return True

        w.register(wd.Component("svc", health, recover=recover))
        clock.advance(10)
        e1 = w.check("svc")   # intento 1: recuperacion declarada pero no verificada
        self.assertTrue(e1["restarted"])
        self.assertFalse(e1["verified"])
        clock.advance(10)
        e2 = w.check("svc")   # segundo fallo consecutivo: el circuito se abre
        self.assertEqual(e2["circuit"], "open")
        clock.advance(31)
        state["cure"] = True
        e3 = w.check("svc")   # prueba semiabierta: cura verificada -> cerrado
        self.assertTrue(e3["probe"])
        self.assertTrue(e3["restarted"])
        self.assertTrue(e3["verified"])
        self.assertEqual(e3["circuit"], "closed")
        self.assertEqual(w.circuit_states()["svc"], "closed")

    def test_circuito_semiabierto_que_falla_reabre(self):
        """La prueba semiabierta que no verifica reabre el circuito."""
        w, clock = self._watchdog(circuit_reset_s=30.0)
        w.register(wd.Component("muerto", lambda: False, recover=lambda: True))
        clock.advance(10)
        w.check("muerto")   # intento 1
        clock.advance(10)
        e2 = w.check("muerto")  # intento 2: abre el circuito
        self.assertEqual(e2["circuit"], "open")
        clock.advance(31)
        e3 = w.check("muerto")  # prueba semiabierta: falla, el circuito reabre
        self.assertTrue(e3["probe"])
        self.assertTrue(e3["restarted"])
        self.assertFalse(e3["verified"])
        self.assertEqual(e3["circuit"], "open")
        clock.advance(1)
        e4 = w.check("muerto")
        self.assertEqual(e4["circuit"], "open")
        self.assertFalse(e4["restarted"])
        self.assertTrue(e4["exhausted"])

    def test_backoff_progresivo(self):
        w, clock = self._watchdog(backoff_factor=3.0, max_restarts=6)
        w.register(wd.Component("svc", lambda: False, recover=lambda: True))
        clock.advance(10)
        w.check("svc")        # intento 1: espera base (cooldown)
        clock.advance(6)
        e2 = w.check("svc")   # tras 1 intento la espera sigue siendo la base
        self.assertTrue(e2["restarted"])
        clock.advance(6)
        e3 = w.check("svc")   # tras 2 intentos la espera es 5 * 3 = 15: bloqueado
        self.assertFalse(e3["restarted"])
        self.assertIn("backoff_remaining_s", e3)
        clock.advance(10)
        e4 = w.check("svc")   # 16 s desde el intento 2: permitido
        self.assertTrue(e4["restarted"])

    def test_backoff_acotado_por_maximo(self):
        w, clock = self._watchdog(backoff_factor=10.0, backoff_max_s=12.0, max_restarts=6)
        w.register(wd.Component("svc", lambda: False, recover=lambda: True))
        clock.advance(10)
        w.check("svc")
        clock.advance(6)
        w.check("svc")        # 2 intentos; la espera teorica seria 50, acotada a 12
        clock.advance(13)
        e3 = w.check("svc")
        self.assertTrue(e3["restarted"])

    def test_sin_reinicios_permitidos_marca_agotado(self):
        clock = FakeClock()
        w = wd.Watchdog(max_restarts=0, cooldown_s=1.0, clock=clock, sleeper=lambda s: None)
        calls = []

        def recover():
            calls.append(1)
            return True

        w.register(wd.Component("svc", lambda: False, recover=recover))
        e = w.check("svc")
        self.assertFalse(e["restarted"])
        self.assertTrue(e["exhausted"])
        self.assertEqual(calls, [])


class RunLoopTests(unittest.TestCase):
    def test_apagado_limpio_con_request_stop(self):
        clock = FakeClock()
        w = wd.Watchdog(clock=clock, sleeper=lambda s: clock.advance(s))
        w.register(wd.Component("ok", lambda: True))
        passes = []

        def stop_after_two(report):
            passes.append(report)
            if len(passes) >= 2:
                w.request_stop()

        code = w.run_loop(1.0, on_pass=stop_after_two)
        self.assertEqual(code, 0)
        self.assertEqual(len(passes), 2)
        self.assertTrue(w.stop_requested)
        events = [e.get("event") for e in w.log_entries() if "event" in e]
        self.assertIn("watchdog_stop_clean", events)

    def test_run_loop_sale_tras_el_limite_de_errores_internos(self):
        clock = FakeClock()
        w = wd.Watchdog(clock=clock, sleeper=lambda s: clock.advance(s))
        errs = []
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            raise RuntimeError("fallo interno")

        w.run_once = flaky  # inyección de fallo interno controlada
        code = w.run_loop(1.0, on_error=lambda n, e: errs.append(str(e)), max_errors=3)
        self.assertEqual(code, 3)
        self.assertEqual(len(errs), 3)
        self.assertEqual(calls["n"], 3)
        events = [e.get("event") for e in w.log_entries() if "event" in e]
        self.assertIn("watchdog_abort_errors", events)


class FromConfigTests(unittest.TestCase):
    def test_watchdog_from_config_registra_componentes(self):
        w = wd.watchdog_from_config()
        names = set(w._components)
        self.assertEqual(names, {"config", "agent_isolation", "vault", "nke"})

    def test_run_once_con_config_real(self):
        w = wd.watchdog_from_config()
        r = w.run_once()
        self.assertIn(r["overall"], ("ok", "degraded", "failed"))
        self.assertEqual(len(r["components"]), 4)


class CliTests(unittest.TestCase):
    def test_main_once_json(self):
        import contextlib, io, json as js
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = wd.main(["--json"])
        self.assertEqual(code, 0)
        data = js.loads(out.getvalue())
        self.assertIn("overall", data)

    def test_main_diagnose(self):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = wd.main(["--diagnose"])
        self.assertIn("Diagnóstico", out.getvalue())
        self.assertIn(code, (0, 1))


if __name__ == "__main__":
    unittest.main()
