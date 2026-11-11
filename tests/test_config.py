import json
import tempfile
import unittest
from pathlib import Path

from nexora import __version__
from nexora.core.config import ConfigError, find_secret_like, load_config, validate_config

NO_USER = Path("/nonexistent/user.json")


class ConfigTests(unittest.TestCase):
    def test_defaults_load_and_match_package_version(self):
        cfg = load_config(user_path=NO_USER)
        self.assertEqual(cfg["version"], __version__)
        self.assertEqual(cfg["agent_memory_policy"], "isolated_per_mode")
        self.assertFalse(cfg["telemetry"]["enabled"])

    def test_shipped_example_user_config_is_valid_and_secret_free(self):
        root = Path(__file__).resolve().parents[1]
        example = json.loads((root / "config" / "user.example.json").read_text())
        self.assertEqual(find_secret_like(example), [])

    def test_user_config_merges_over_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "user.json"
            p.write_text(json.dumps({"preferred_browser": "librewolf", "ai_engine": {"backend": "ollama"}}))
            cfg = load_config(user_path=p)
        self.assertEqual(cfg["preferred_browser"], "librewolf")
        self.assertEqual(cfg["ai_engine"]["backend"], "ollama")
        self.assertEqual(cfg["ai_engine"]["model"], "nexora-local-q4")  # heredado

    def test_secrets_in_config_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ({"api_key": "abc"}, {"connected_services": [{"password": "x"}]},
                        {"local_model_endpoint": "http://user:pw@127.0.0.1:11434"}):
                p = Path(d) / "user.json"
                p.write_text(json.dumps(bad))
                with self.assertRaises(ConfigError, msg=str(bad)):
                    load_config(user_path=p)

    def test_locked_and_invalid_values(self):
        base = load_config(user_path=NO_USER)
        for patch in ({"agent_memory_policy": "shared"}, {"preferred_browser": "chrome"},
                      {"browsers": ["chrome"]}, {"modes_enabled": ["nope"]},
                      {"ai_engine": {"backend": "cloud"}}, {"telemetry": {"enabled": "yes"}},
                      {"meteorology": {"provider": "x"}}, {"vault": {"backend": "plain-json"}}):
            cfg = {**base, **patch}
            with self.assertRaises(ConfigError, msg=str(patch)):
                validate_config(cfg)

    def test_invalid_json_and_missing_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "user.json"
            p.write_text("{not json")
            with self.assertRaises(ConfigError):
                load_config(user_path=p)
            with self.assertRaises(ConfigError):
                load_config(config_dir=Path(d), user_path=NO_USER)


if __name__ == "__main__":
    unittest.main()
