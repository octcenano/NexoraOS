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
        state = {"n": 0}
        def check():
            return state["n"] > 0
        def recover():
            state["n"] += 1
            return True
        w.register(wd.Component("svc", check, recover=recover))
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
