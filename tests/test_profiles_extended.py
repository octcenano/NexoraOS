import unittest

from nexora.core.profiles import (
    calculate_hybrid_profile,
    detect_gpu,
    detect_hardware,
    detect_storage_gb,
    suggest_tier,
)


class HardwareDetectionTests(unittest.TestCase):
    def test_detect_gpu_returns_tuple_of_strings(self):
        gpus = detect_gpu()
        self.assertIsInstance(gpus, tuple)
        for g in gpus:
            self.assertIsInstance(g, str)

    def test_detect_storage_gb_returns_float_or_none(self):
        value = detect_storage_gb()
        self.assertTrue(value is None or (isinstance(value, float) and value >= 0))

    def test_detect_storage_on_missing_path_is_none(self):
        self.assertIsNone(detect_storage_gb("/no/existe/esta/ruta"))

    def test_detect_hardware_fields_or_none(self):
        hw = detect_hardware()
        if hw is not None:
            self.assertGreaterEqual(hw.cpu_cores, 1)
            self.assertGreater(hw.ram_gb, 0)
            self.assertIsInstance(hw.gpus, tuple)
            self.assertTrue(hw.source)


class SuggestTierTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(suggest_tier(2, 4), "compact")
        self.assertEqual(suggest_tier(1, 64), "compact")   # pocos núcleos mandan
        self.assertEqual(suggest_tier(8, 16), "expanded")
        self.assertEqual(suggest_tier(8, 15.9), "balanced")
        self.assertEqual(suggest_tier(4, 8), "balanced")


class ProfileTests(unittest.TestCase):
    def test_manual_ignores_suggestion_and_keeps_it(self):
        prof = calculate_hybrid_profile("manual", 8, 32, manual_limits={"concurrent_agents": 9})
        self.assertEqual(prof["name"], "user-controlled")
        self.assertEqual(prof["limits"], {"concurrent_agents": 9})
        self.assertEqual(prof["suggested"], "expanded")

    def test_downgrade_never_warns(self):
        prof = calculate_hybrid_profile("compact", 8, 32)
        self.assertNotIn("warning", prof)

    def test_upgrade_warns(self):
        prof = calculate_hybrid_profile("expanded", 2, 4)
        self.assertIn("warning", prof)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            calculate_hybrid_profile("auto", 0, 4)
        with self.assertRaises(ValueError):
            calculate_hybrid_profile("auto", 4, -1)
        with self.assertRaises(ValueError):
            calculate_hybrid_profile("turbo", 4, 8)


if __name__ == "__main__":
    unittest.main()
