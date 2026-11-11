import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from nexora import __version__
from nexora.core.config import ConfigError, load_config, write_user_config

NO_USER = Path("/nonexistent/user.json")


class ConfigExtendedTests(unittest.TestCase):
    def setUp(self):
        os.environ["NEXORA_USER_CONFIG"] = "/nonexistent/user.json"

    def tearDown(self):
        os.environ.pop("NEXORA_USER_CONFIG", None)

    def test_unknown_top_level_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "user.json"
            p.write_text(json.dumps({"totally_unknown_key": 1}))
            with self.assertRaises(ConfigError):
                load_config(user_path=p)

    def test_corrupt_defaults_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "defaults.json").write_text("{corrupto")
            with self.assertRaises(ConfigError):
                load_config(config_dir=Path(d), user_path=NO_USER)

    def test_defaults_as_non_object_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "defaults.json").write_text("[1, 2, 3]")
            with self.assertRaises(ConfigError):
                load_config(config_dir=Path(d), user_path=NO_USER)

    def test_write_user_config_creates_safe_dirs_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "nested" / "nexora" / "user.json"
            base = load_config(user_path=NO_USER)
            write_user_config(base, path=target)
            self.assertEqual(oct(stat.S_IMODE(target.parent.stat().st_mode)), "0o700")
            self.assertEqual(oct(stat.S_IMODE(target.stat().st_mode)), "0o600")
            cfg = load_config(user_path=target)
            self.assertEqual(cfg["version"], __version__)

    def test_write_user_config_rejects_secrets_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ConfigError):
                write_user_config({"api_key": "x"}, path=Path(d) / "user.json")
            base = {"version": __version__, "telemetry": {"enabled": "yes"}}
            with self.assertRaises(ConfigError):
                write_user_config(base, path=Path(d) / "user.json")

    def test_write_user_config_is_atomic_no_temp_leftovers(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "user.json"
            base = load_config(user_path=NO_USER)
            write_user_config(base, path=target)
            leftovers = [p for p in Path(d).iterdir() if p.name != "user.json"]
            self.assertEqual(leftovers, [])

    def test_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base = load_config(user_path=NO_USER)
            base = {**base, "version": "9.9.9"}
            p = Path(d) / "user.json"
            p.write_text(json.dumps(base))
            with self.assertRaises(ConfigError):
                load_config(user_path=p)


if __name__ == "__main__":
    unittest.main()
