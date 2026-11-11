import unittest

from nexora.agents.base import AgentMessage, BaseAgent
from nexora.core.registry import ModeRegistry


class AgentIsolationTests(unittest.TestCase):
    def setUp(self):
        self.forge = BaseAgent("ForgeAgent", mode="forge")
        self.meteo = BaseAgent("MeteoAgent", mode="meteorology")

    def test_other_agent_cannot_see_private_memory(self):
        self.forge.remember("plan", {"x": 1})
        self.assertIsNone(self.meteo.recall("plan"))
        self.assertEqual(self.meteo.memory_keys(), ())

    def test_recall_returns_copy(self):
        self.forge.remember("k", {"a": [1]})
        self.forge.recall("k")["a"].append(2)
        self.assertEqual(self.forge.recall("k"), {"a": [1]})

    def test_share_requires_user_approval(self):
        self.forge.remember("k", 1)
        with self.assertRaises(PermissionError):
            self.forge.share_with(self.meteo, ["k"], "demo")
        self.assertEqual(self.meteo.inbox(), ())

    def test_approved_share_goes_to_inbox_not_memory(self):
        self.forge.remember("k", 1)
        self.forge.remember("secret", 2)
        msg = self.forge.share_with(self.meteo, ["k"], "demo", user_approved=True)
        self.assertEqual(dict(msg.data), {"k": 1})
        self.assertEqual(self.meteo.inbox()[0].source, "forge")
        self.assertEqual(self.meteo.memory_keys(), ())

    def test_share_unknown_key_fails(self):
        with self.assertRaises(KeyError):
            self.forge.share_with(self.meteo, ["nope"], "demo", user_approved=True)

    def test_message_validation(self):
        with self.assertRaises(ValueError):
            AgentMessage("forge", "forge", "x")
        with self.assertRaises(ValueError):
            AgentMessage("forge", "office", " ")
        with self.assertRaises(ValueError):
            self.meteo.receive(AgentMessage("forge", "office", "x"))

    def test_describe_and_namespace(self):
        d = self.forge.describe()
        self.assertEqual(d["memory_namespace"], "agents/forge/")
        self.assertFalse(d["shared_private_memory"])


class RegistryTests(unittest.TestCase):
    def test_all_modes_create_agents_of_their_mode(self):
        reg = ModeRegistry()
        for mode in reg.names():
            self.assertEqual(reg.create_agent(mode).mode, mode)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            ModeRegistry().create_agent("nope")

    def test_agent_uses_engine_and_reports_errors(self):
        class Boom:
            def query(self, prompt, system_context=None):
                return {"status": "error", "message": "caÃ­do"}
        out = ModeRegistry().create_agent("forge", engine=Boom()).process_prompt("hola")
        self.assertIn("caÃ­do", out)


if __name__ == "__main__":
    unittest.main()
