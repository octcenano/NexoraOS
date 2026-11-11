"""
Unit tests for NEXORA OS Core & Beta 0.2 modules
"""

import unittest
from nexora.core.registry import ModeRegistry
from nexora.core.profiles import calculate_hybrid_profile
from nexora.connectors.account_hub import AccountHub
from nexora.connectors.browser import BrowserConnector
from nexora.agents.base import BaseAgent
from nexora.agents.meteorology import MeteorologyAgent
from nexora.core.ai_engine import LocalAIEngine
from nexora.core.vault import SecureVault
from nexora.ui.dashboard import NexoraDashboard

class NexoraTests(unittest.TestCase):

    def test_agent_memory_isolated(self):
        agent_a = BaseAgent("AgentA", mode="forge")
        agent_b = BaseAgent("AgentB", mode="meteorology")
        agent_a.remember("key", "forge_secret")
        agent_b.remember("key", "meteo_secret")
        self.assertEqual(agent_a.recall("key"), "forge_secret")
        self.assertEqual(agent_b.recall("key"), "meteo_secret")

    def test_account_hub_requires_authorization(self):
        hub = AccountHub()
        hub.register_connection("github", "GitHub API", ["repo", "user"])
        self.assertFalse(hub.is_authorized("github"))

    def test_both_browsers_supported(self):
        conn = BrowserConnector()
        self.assertIn("firefox", conn.supported_browsers)
        self.assertIn("librewolf", conn.supported_browsers)

    def test_compact_profile(self):
        prof = calculate_hybrid_profile("auto", cpu_cores=2, ram_gb=4)
        self.assertEqual(prof["name"], "compact")

    def test_manual_profile(self):
        prof = calculate_hybrid_profile("manual", cpu_cores=8, ram_gb=32)
        self.assertEqual(prof["name"], "user-controlled")

    def test_ai_engine_local_query(self):
        engine = LocalAIEngine()
        res = engine.query("Hola Nexora")
        self.assertEqual(res["status"], "success")

    def test_secure_vault(self):
        vault = SecureVault()
        vault.set_secret("token", "xyz123")
        self.assertEqual(vault.get_secret("token"), "xyz123")
        vault.revoke_secret("token")
        self.assertIsNone(vault.get_secret("token"))

    def test_gui_dashboard_switch_mode(self):
        dash = NexoraDashboard()
        self.assertTrue(dash.switch_mode("meteorology"))
        self.assertEqual(dash.active_mode, "meteorology")

    def test_meteorology_agent_attribution(self):
        meteo = MeteorologyAgent()
        obs = meteo.get_weather_observation("Madrid")
        self.assertIn("attribution", obs)
        self.assertEqual(obs["location"], "Madrid")

if __name__ == "__main__":
    unittest.main()
