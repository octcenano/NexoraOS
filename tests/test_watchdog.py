"""Tests del watchdog: recuperación acotada, cooldown, agotamiento, diagnóstico y anti-bucle."""

import unittest

from nexora.watchdog import Component, Watchdog, watchdog_from_config


class FakeClock:
    def __init__(self):
        # Arranca en un instante lejano para que el primer intento de
        # recuperación no esté dentro del cooldown (como con time.monotonic real).
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class WatchdogTest(unittest.TestCase):
    def _wd(self, max_restarts=2, cooldown=5.0):
        clock = FakeClock()
        sleeps = []
        wd = Watchdog(max_restarts=max_restarts, cooldown_s=cooldown,
                      clock=clock, sleeper=sleeps.append)
        return wd, clock, sleeps

    def test_componente_sano(self):
        wd, _, _ = self._wd()
        wd.register(Component("ok", lambda: True))
        report = wd.run_once()
        self.assertEqual(report["overall"], "ok")

    def test_recuperacion_limitada(self):
        wd, clock, _ = self._wd(max_restarts=2, cooldown=0.0)
        state = {"n": 0}

        def unhealthy():
            return state["n"] >= 2

        def recover():
            state["n"] = 2
            return True

        wd.register(Component("svc", unhealthy, recover=recover))
        r1 = wd.check("svc")
        self.assertFalse(r1["healthy"])
        self.assertTrue(r1["restarted"])
        self.assertTrue(r1["recovered"])
        r2 = wd.check("svc")
        self.assertTrue(r2["healthy"])
        self.assertEqual(wd.restart_count("svc"), 1)

    def test_cooldown_evita_recuperaciones_inmediatas(self):
        wd, clock, _ = self._wd(max_restarts=3, cooldown=10.0)
        calls = {"n": 0}

        def recover():
            calls["n"] += 1
            return True

        wd.register(Component("svc", lambda: False, recover=recover))
        wd.check("svc")
        wd.check("svc")  # dentro del cooldown: no reintenta
        self.assertEqual(calls["n"], 1)
        clock.advance(10.0)
        wd.check("svc")
        self.assertEqual(calls["n"], 2)

    def test_agotamiento_de_reinicios(self):
        wd, _, _ = self._wd(max_restarts=1, cooldown=0.0)
        wd.register(Component("svc", lambda: False, recover=lambda: False))
        wd.check("svc")
        r = wd.check("svc")
        self.assertTrue(r["exhausted"])
        report = wd.run_once()
        self.assertEqual(report["overall"], "failed")

    def test_health_check_que_lanza_no_derriba(self):
        wd, _, _ = self._wd()
        def bad():
            raise RuntimeError("boom")
        wd.register(Component("bad", bad))
        r = wd.check("bad")
        self.assertFalse(r["healthy"])
        self.assertIn("error", r)

    def test_componente_desconocido(self):
        wd, _, _ = self._wd()
        with self.assertRaises(KeyError):
            wd.check("no-existe")

    def test_duplicado(self):
        wd, _, _ = self._wd()
        wd.register(Component("a", lambda: True))
        with self.assertRaises(ValueError):
            wd.register(Component("a", lambda: True))

    def test_incidencias_y_diagnostico(self):
        wd, _, _ = self._wd(max_restarts=0)
        wd.register(Component("svc", lambda: False))
        wd.check("svc")
        incs = wd.incidents()
        self.assertEqual(len(incs), 1)
        self.assertEqual(incs[0]["component"], "svc")
        diag = wd.diagnose()
        self.assertEqual(diag["scope"], "diagnostic_no_side_effects")
        self.assertEqual(len(diag["incidents"]), 1)
        self.assertTrue(any("svc" in r for r in diag["recommendations"]))

    def test_watchdog_from_config_registra_componentes(self):
        wd = watchdog_from_config({"vault": {"backend": "memory"}})
        report = wd.run_once()
        self.assertIn(report["overall"], ("ok", "degraded", "failed"))
        names = {r["component"] for r in report["components"]}
        self.assertEqual(names, {"config", "agent_isolation", "vault"})


if __name__ == "__main__":
    unittest.main()
