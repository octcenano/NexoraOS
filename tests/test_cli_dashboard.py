import contextlib
import io
import json
import os
import unittest

from nexora import __version__
from nexora.cli import main
from nexora.connectors.account_hub import AccountHub
from nexora.core.ai_engine import LocalAIEngine
from nexora.diagnostics.health import health_report
from nexora.ui.dashboard import NexoraDashboard


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        os.environ["NEXORA_USER_CONFIG"] = "/nonexistent/user.json"

    def tearDown(self):
        os.environ.pop("NEXORA_USER_CONFIG", None)

    def test_no_command(self):
        code, out, _ = run()
        self.assertEqual(code, 0)
        self.assertIn(__version__, out)

    def test_modes(self):
        code, out, _ = run("modes")
        self.assertEqual(code, 0)
        for m in ("FORGE", "METEOROLOGY", "SECURITY", "CREATOR", "OFFICE"):
            self.assertIn(m, out)

    def test_profile_explicit_and_warning(self):
        code, out, _ = run("profile", "--cpu-cores", "2", "--ram-gb", "4")
        self.assertEqual((code, "compact" in out), (0, True))
        _, out, _ = run("profile", "--profile", "expanded", "--cpu-cores", "2", "--ram-gb", "4")
        self.assertIn("AVISO", out)
        code, _, err = run("profile", "--cpu-cores", "0", "--ram-gb", "4")
        self.assertEqual(code, 2)

    def test_dashboard_text_and_json(self):
        code, out, _ = run("dashboard")
        self.assertIn("[forge]", out)
        _, out, _ = run("dashboard", "--mode", "meteorology", "--json")
        data = json.loads(out)
        self.assertEqual(data["active_mode"], "meteorology")
        self.assertEqual(data["widgets"]["active_agent"], "MeteorologyAgent")
        self.assertEqual(run("dashboard", "--mode", "nope")[0], 2)

    def test_health_never_fails_on_clean_install(self):
        code, out, _ = run("health")
        self.assertEqual(code, 0)
        self.assertIn("watchdogs", out)

    def test_weather_simulated_by_default_is_labelled(self):
        code, out, _ = run("weather", "Madrid")
        self.assertEqual(code, 0)
        self.assertIn("[SIMULADO]", out)

    def test_ask_warns_when_simulated(self):
        code, out, err = run("ask", "hola", "--mode", "office")
        self.assertEqual(code, 0)
        self.assertIn("simulado", err)
        self.assertEqual(run("ask", "hola", "--mode", "nope")[0], 2)

    def test_bad_config_gives_exit_2(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"api_key": "x"}, f)
        os.environ["NEXORA_USER_CONFIG"] = f.name
        try:
            self.assertEqual(run("modes")[0], 2)
        finally:
            os.unlink(f.name)


class DashboardTests(unittest.TestCase):
    def test_invalid_mode_rejected_and_state_unchanged(self):
        dash = NexoraDashboard()
        self.assertFalse(dash.switch_mode("nope"))
        self.assertEqual(dash.active_mode, "forge")

    def test_agent_memory_survives_mode_switch_but_stays_private(self):
        dash = NexoraDashboard()
        dash.active_agent.remember("k", "forge-data")
        dash.switch_mode("meteorology")
        self.assertIsNone(dash.active_agent.recall("k"))
        dash.switch_mode("forge")
        self.assertEqual(dash.active_agent.recall("k"), "forge-data")

    def test_widgets_reflect_account_hub_live(self):
        hub = AccountHub()
        dash = NexoraDashboard(hub=hub)
        self.assertEqual(dash.widgets["account_hub_status"], "disconnected")
        hub.register_connection("github", "api", ["repo"])
        hub.grant("github")
        self.assertEqual(dash.widgets["account_hub_status"], "connected")

    def test_ask_goes_through_active_agent_and_engine(self):
        dash = NexoraDashboard(engine=LocalAIEngine())
        dash.switch_mode("meteorology")
        self.assertIn("simulada", dash.ask("Â¿lloverÃ¡ maÃ±ana?"))


class HealthTests(unittest.TestCase):
    def test_report_structure(self):
        rep = health_report()
        names = {c["name"] for c in rep["checks"]}
        self.assertTrue({"python", "config", "agent_isolation", "vault", "ai_engine", "browsers"} <= names)
        self.assertEqual(rep["capabilities"]["iso_builder"], "not_implemented")


if __name__ == "__main__":
    unittest.main()
