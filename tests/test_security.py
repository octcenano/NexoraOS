import unittest

from nexora.agents.security import SecurityAgent, run_defensive_audit


class SecurityAgentTests(unittest.TestCase):
    def test_agent_mode_and_describe_declare_readonly(self):
        agent = SecurityAgent()
        self.assertEqual(agent.mode, "security")
        info = agent.describe()
        self.assertEqual(info["tools"], ["defensive_audit_readonly"])
        self.assertFalse(info["offensive_capabilities"])

    def test_audit_returns_checks_and_overall(self):
        report = run_defensive_audit()
        names = {c["name"] for c in report["checks"]}
        self.assertTrue({"config", "vault", "listening_sockets", "world_writable_files"} <= names)
        self.assertIn(report["overall"], ("ok", "warn", "fail"))
        self.assertEqual(report["scope"], "read_only_defensive")

    def test_audit_is_read_only(self):
        # La auditoría no debe crear ni modificar archivos de usuario.
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_CONFIG_HOME"] = d
            try:
                before = sorted(str(p) for p in Path(d).rglob("*"))
                run_defensive_audit()
                after = sorted(str(p) for p in Path(d).rglob("*"))
                self.assertEqual(before, after)
            finally:
                os.environ.pop("XDG_CONFIG_HOME", None)

    def test_agent_stores_last_audit_in_private_memory(self):
        agent = SecurityAgent()
        agent.audit()
        self.assertIn("last_audit", agent.memory_keys())


if __name__ == "__main__":
    unittest.main()
