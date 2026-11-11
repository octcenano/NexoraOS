"""Fase 5: los cinco modos oficiales y sus niveles de intensidad."""

import json
import unittest
from pathlib import Path

from nexora.core.registry import INTENSITY_LEVELS, MODES, SPECIALIST_AGENTS, ModeRegistry
from nexora.core.resources import LEVELS, level_policy


class OfficialModesTests(unittest.TestCase):
    def test_exactly_the_five_official_modes(self):
        self.assertEqual(set(ModeRegistry().names()),
                         {"gaming", "hacking", "office", "stealth", "forge"})

    def test_specialists_are_not_modes(self):
        for name in ("creator", "meteorology", "security"):
            self.assertNotIn(name, MODES)
        self.assertIn("meteorology", SPECIALIST_AGENTS)
        self.assertIn("security", SPECIALIST_AGENTS)

    def test_every_mode_has_valid_default_intensity_and_effects(self):
        for mode, spec in MODES.items():
            self.assertIn(spec["default_intensity"], INTENSITY_LEVELS, mode)
            self.assertEqual(set(spec["effects"]), set(INTENSITY_LEVELS), mode)

    def test_set_intensity_validates_mode_and_level(self):
        reg = ModeRegistry()
        reg.set_intensity("gaming", "3")
        self.assertEqual(reg.intensity("gaming"), "3")
        with self.assertRaises(ValueError):
            reg.set_intensity("nope", "1")
        with self.assertRaises(ValueError):
            reg.set_intensity("gaming", "11")

    def test_intensity_policy_maps_to_real_level_policies(self):
        reg = ModeRegistry()
        mapping = {"1": "level1", "2": "level2", "3": "level3", "full": "full"}
        for level, expected in mapping.items():
            info = reg.intensity_policy("forge", level)
            self.assertEqual(info["policy"], level_policy(expected))
        # Solo 'full' declara ajuste agresivo (y exige aprobación).
        for level in ("1", "2", "3"):
            self.assertFalse(reg.intensity_policy("gaming", level)["policy"].aggressive_tuning)
        self.assertTrue(reg.intensity_policy("gaming", "full")["policy"].aggressive_tuning)

    def test_intensity_policy_rejects_unknown(self):
        reg = ModeRegistry()
        with self.assertRaises(ValueError):
            reg.intensity_policy("nope")
        with self.assertRaises(ValueError):
            reg.intensity_policy("forge", "turbo")

    def test_levels_declared_in_resources_are_four(self):
        self.assertEqual(set(LEVELS), {"level1", "level2", "level3", "full"})

    def test_defaults_json_declares_official_modes(self):
        data = json.loads((Path(__file__).resolve().parents[1] / "config" / "defaults.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data["modes_enabled"]), {"gaming", "hacking", "office", "stealth", "forge"})

    def test_coordinator_accepts_official_and_rejects_specialist_modes(self):
        from nexora.core.coordinator import Coordinator

        coord = Coordinator()
        self.assertEqual(coord.submit("local_ai", "forge", "prueba").status, "ok")
        self.assertEqual(coord.submit("local_ai", "gaming", "prueba").status, "ok")
        res = coord.submit("local_ai", "creator", "prueba")
        self.assertEqual(res.status, "denied")
        # Hacking no puede usar herramientas fuera de su política.
        res = coord.submit("execute_commands", "hacking", "borrar archivos", user_approved=True)
        self.assertEqual(res.status, "denied")

    def test_hacking_mode_declares_no_offensive_autonomy(self):
        reg = ModeRegistry()
        pol = reg.tool_policy("hacking")
        self.assertIn("defensive_audit_readonly", pol.allowed_tools)
        self.assertNotIn("execute_commands", pol.allowed_tools)


if __name__ == "__main__":
    unittest.main()
