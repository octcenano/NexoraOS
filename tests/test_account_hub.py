import unittest

from nexora.connectors.account_hub import AccountHub
from nexora.connectors.browser import BrowserConnector


class AccountHubTests(unittest.TestCase):
    def setUp(self):
        self.hub = AccountHub()
        self.hub.register_connection("github", "GitHub API", ["repo", "user"], secret_ref="github-token")

    def test_lifecycle(self):
        self.assertEqual(self.hub.get_state("github"), "pending_authorization")
        self.assertFalse(self.hub.may_access("github", "repo"))
        self.hub.grant("github")
        self.assertTrue(self.hub.is_authorized("github"))
        self.assertTrue(self.hub.may_access("github", "repo"))
        self.assertFalse(self.hub.may_access("github", "admin"))
        self.hub.mark_expired("github")
        self.assertFalse(self.hub.may_access("github", "repo"))

    def test_revoke_and_no_silent_regrant(self):
        self.hub.grant("github")
        self.hub.revoke("github")
        self.assertEqual(self.hub.get_state("github"), "revoked")
        with self.assertRaises(ValueError):
            self.hub.grant("github")

    def test_unknown_service(self):
        self.assertEqual(self.hub.get_state("x"), "not_configured")
        self.assertFalse(self.hub.may_access("x", "repo"))
        with self.assertRaises(KeyError):
            self.hub.grant("x")

    def test_only_reference_to_secret_is_stored(self):
        conn = self.hub.list_connections()["github"]
        self.assertEqual(conn["secret_ref"], "github-token")
        self.assertNotIn("secret", [k for k in conn if k != "secret_ref"])

    def test_summary_and_validation(self):
        self.assertEqual(self.hub.summary(), "pending_authorization")
        self.hub.grant("github")
        self.assertEqual(self.hub.summary(), "connected")
        with self.assertRaises(ValueError):
            self.hub.register_connection("", "x")

    def test_list_connections_is_a_copy(self):
        self.hub.list_connections()["github"]["state"] = "connected"
        self.assertFalse(self.hub.is_authorized("github"))


class BrowserTests(unittest.TestCase):
    def test_single_and_invalid_browser(self):
        self.assertEqual(BrowserConnector("librewolf").selected, ("librewolf",))
        self.assertEqual(BrowserConnector().selected, ("firefox", "librewolf"))
        with self.assertRaises(ValueError):
            BrowserConnector("chrome")

    def test_status_never_extracts_secrets(self):
        self.assertFalse(BrowserConnector("firefox").status()["secret_extraction"])
        self.assertEqual(set(BrowserConnector.detect_installed()), {"firefox", "librewolf"})


if __name__ == "__main__":
    unittest.main()
