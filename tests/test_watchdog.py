import unittest

from nexora.watchdog import Component, Watchdog, watchdog_from_config


class WatchdogTests(unittest.TestCase):
    def test_healthy_component_reports_ok(self):
        wd = Watchdog()
        wd.register(Component("a", lambda: True))
        report = wd.run_once()
        self.assertEqual(report["overall"], "ok")
        self.assertTrue(report["components"][0]["healthy"])

    def test_failing_component_without_recovery_is_degraded(self):
        wd = Watchdog()
        wd.register(Component("a", lambda: False))
        report = wd.run_once()
        self.assertEqual(report["overall"], "degraded")

    def test_recovery_is_bounded(self):
        calls = {"recover": 0}

        def recover():
            calls["recover"] += 1
            return False  # la recuperación nunca funciona

        wd = Watchdog(max_restarts=2, cooldown_s=0.0)
        wd.register(Component("a", lambda: False, recover=recover))
        for _ in range(5):
            wd.check("a")
        self.assertEqual(calls["recover"], 2)  # acotado por max_restarts
        self.assertEqual(wd.restart_count("a"), 2)
        # tras agotar, no se reintenta más
        wd.check("a")
        self.assertEqual(calls["recover"], 2)

    def test_cooldown_delays_restarts(self):
        calls = {"recover": 0}
        clock = {"t": 0.0}

        def recover():
            calls["recover"] += 1
            return True

        wd = Watchdog(max_restarts=5, cooldown_s=10.0, clock=lambda: clock["t"])
        wd.register(Component("a", lambda: False, recover=recover))
        wd.check("a")
        clock["t"] += 1.0  # dentro del cooldown
        wd.check("a")
        self.assertEqual(calls["recover"], 1)
        clock["t"] += 20.0  # fuera del cooldown
        wd.check("a")
        self.assertEqual(calls["recover"], 2)

    def test_health_check_exception_does_not_crash_watchdog(self):
        def boom():
            raise RuntimeError("x")

        wd = Watchdog()
        wd.register(Component("a", boom))
        entry = wd.check("a")
        self.assertFalse(entry["healthy"])
        self.assertIn("RuntimeError", entry.get("error", ""))

    def test_log_is_bounded(self):
        wd = Watchdog(log_size=3)
        wd.register(Component("a", lambda: False))
        for _ in range(10):
            wd.check("a")
        self.assertEqual(len(wd.log_entries()), 3)

    def test_unknown_component_and_duplicates(self):
        wd = Watchdog()
        with self.assertRaises(KeyError):
            wd.check("nope")
        wd.register(Component("a", lambda: True))
        with self.assertRaises(ValueError):
            wd.register(Component("a", lambda: True))

    def test_overall_failed_when_exhausted(self):
        wd = Watchdog(max_restarts=0, cooldown_s=0.0)
        wd.register(Component("a", lambda: False, recover=lambda: True))
        wd.check("a")
        report = wd.run_once()
        self.assertEqual(report["overall"], "failed")

    def test_watchdog_from_config_registers_core_components(self):
        wd = watchdog_from_config()
        names = {c.name for c in wd._components.values()}
        self.assertIn("config", names)
        self.assertIn("agent_isolation", names)
        self.assertIn("vault", names)


if __name__ == "__main__":
    unittest.main()
