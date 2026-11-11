"""Tests del núcleo adaptativo: inventario, niveles y perfiles híbridos."""

import unittest

from nexora.core import resources
from nexora.core.resources import (
    LEVELS,
    ModeShare,
    build_allocation,
    inventory,
    level_policy,
    read_battery,
    read_cpu_cores,
    read_ram_gb,
    read_storage_gb,
)


class InventoryTests(unittest.TestCase):
    def test_ram_y_cpu_legibles_o_none(self):
        ram = read_ram_gb()
        cores = read_cpu_cores()
        self.assertTrue(ram is None or ram > 0)
        self.assertTrue(cores is None or cores >= 1)

    def test_inventario_nunca_inventa_datos(self):
        inv = inventory()
        self.assertIn("cpu_cores", inv)
        self.assertIn("ram_gb", inv)
        self.assertIsInstance(inv["gpus"], list)
        self.assertIsInstance(inv["temperatures_c"], dict)
        if inv["battery"] is not None:
            self.assertIn("status", inv["battery"])

    def test_storage_ruta_inexistente_es_none(self):
        self.assertIsNone(read_storage_gb("/no/existe/esta/ruta"))

    def test_bateria_none_o_valida(self):
        bat = read_battery()
        if bat is not None:
            self.assertTrue(bat["device"].startswith("BAT"))


class LevelPolicyTests(unittest.TestCase):
    def test_los_cuatro_niveles_existen(self):
        self.assertEqual(set(LEVELS), {"level1", "level2", "level3", "full"})

    def test_los_niveles_son_politicas_reales_distintas(self):
        # Cada nivel cambia agentes concurrentes, RAM de modelo y peso de CPU.
        agentes = {name: p.concurrent_agents for name, p in LEVELS.items()}
        rams = {name: p.max_model_ram_gb for name, p in LEVELS.items()}
        self.assertEqual(len(set(agentes.values())), 4)
        self.assertEqual(len(set(rams.values())), 4)

    def test_solo_full_permite_ajuste_agresivo(self):
        for name, p in LEVELS.items():
            self.assertEqual(p.aggressive_tuning, name == "full")

    def test_nivel_desconocido(self):
        with self.assertRaises(ValueError):
            level_policy("turbo")


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.inv = {"cpu_cores": 8, "ram_gb": 16.0, "gpus": ["AMD"],
                    "temperatures_c": {"coretemp/temp1": 45.0}, "battery": None}

    def test_primario_tiene_prioridad_real(self):
        plan = build_allocation(["gaming", "forge"], "level2", inv=self.inv)
        prim = plan.for_mode("gaming")
        sec = plan.for_mode("forge")
        self.assertTrue(prim.primary)
        self.assertFalse(sec.primary)
        self.assertGreater(prim.cpu_weight, sec.cpu_weight)
        self.assertGreater(prim.ram_limit_gb, sec.ram_limit_gb)

    def test_reparto_suma_cien(self):
        plan = build_allocation(["forge", "office", "meteorology"], "level2", inv=self.inv)
        self.assertAlmostEqual(sum(s.cpu_share_pct for s in plan.shares), 100.0, places=1)

    def test_secundario_nunca_supera_al_primario(self):
        plan = build_allocation(["gaming", "security", "meteorology"], "level3", inv=self.inv)
        prim = plan.for_mode("gaming")
        for s in plan.shares:
            if not s.primary:
                self.assertLessEqual(s.ram_limit_gb, prim.ram_limit_gb)
                self.assertLessEqual(s.cpu_weight, prim.cpu_weight)

    def test_la_ram_reservable_no_supera_el_80_por_ciento(self):
        plan = build_allocation(["forge"], "full", inv=self.inv)
        self.assertLessEqual(plan.for_mode("forge").ram_limit_gb, 16.0 * 0.8 + 0.01)

    def test_full_sin_sensores_exige_compatibilidad(self):
        inv = {"cpu_cores": 8, "ram_gb": 32.0, "gpus": [], "temperatures_c": {}, "battery": None}
        plan = build_allocation(["gaming"], "full", inv=inv)
        self.assertTrue(plan.requires_approval)
        self.assertTrue(any("compatibilidad" in w for w in plan.warnings))

    def test_bateria_baja_genera_avisos(self):
        inv = dict(self.inv, battery={"device": "BAT0", "status": "Discharging", "capacity_pct": 12})
        plan = build_allocation(["gaming"], "level3", inv=inv)
        self.assertTrue(any("Batería" in w for w in plan.warnings))

    def test_plan_es_reversible_por_construccion(self):
        # El plan es un valor inmutable: no toca el sistema hasta apply() explícito.
        plan = build_allocation(["gaming", "forge"], "level2", inv=self.inv)
        self.assertIsInstance(plan.for_mode("gaming"), ModeShare)
        self.assertFalse(hasattr(plan, "applied"))

    def test_modos_invalidos(self):
        with self.assertRaises(ValueError):
            build_allocation([], "level2", inv=self.inv)
        with self.assertRaises(ValueError):
            build_allocation(["nope"], "level2", inv=self.inv)
        with self.assertRaises(ValueError):
            build_allocation(["gaming", "gaming"], "level2", inv=self.inv)

    def test_sin_hardware_legible_no_se_reparte_a_ciegas(self):
        with self.assertRaises(ValueError):
            build_allocation(["gaming"], "level2", inv={"cpu_cores": None, "ram_gb": None})


if __name__ == "__main__":
    unittest.main()
