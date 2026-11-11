import unittest

from nexora.core.profiles import calculate_hybrid_profile, detect_hardware, suggest_tier


class ProfileTests(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(suggest_tier(2, 16), "compact")
        self.assertEqual(suggest_tier(8, 4), "compact")
        self.assertEqual(suggest_tier(4, 8), "balanced")
        self.assertEqual(suggest_tier(8, 16), "expanded")

    def test_manual_tier_has_priority_and_warns_when_above_hardware(self):
        prof = calculate_hybrid_profile("expanded", 2, 4)
        self.assertEqual(prof["name"], "expanded")
        self.assertEqual(prof["suggested"], "compact")
        self.assertIn("warning", prof)

    def test_manual_tier_below_hardware_has_no_warning(self):
        self.assertNotIn("warning", calculate_hybrid_profile("compact", 8, 32))

    def test_manual_limits(self):
        prof = calculate_hybrid_profile("manual", 8, 32, manual_limits={"concurrent_agents": 3})
        self.assertEqual(prof["limits"], {"concurrent_agents": 3})

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            calculate_hybrid_profile("auto", 0, 8)
        with self.assertRaises(ValueError):
            calculate_hybrid_profile("auto", 4, 0)
        with self.assertRaises(ValueError):
            calculate_hybrid_profile("turbo", 4, 8)

    def test_detect_hardware_is_sane(self):
        hw = detect_hardware()
        if hw is not None:
            self.assertGreaterEqual(hw.cpu_cores, 1)
            self.assertGreater(hw.ram_gb, 0)


if __name__ == "__main__":
    unittest.main()
