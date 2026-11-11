"""Tests de NKE: capacidades, monitor, analizador, políticas, seguridad, motor y extensión de kernel."""

import os
import tempfile
import unittest
from pathlib import Path

from nexora.nke.analyzer import analyze
from nexora.nke.capabilities import detect_capabilities
from nexora.nke.engine import NKEngine
from nexora.nke.history import NKEHistory
from nexora.nke.monitor import NKMonitor, read_meminfo, top_processes
from nexora.nke.policy import CATEGORY_A, CATEGORY_B, CATEGORY_C, ACTION_CATALOG, PolicyEngine
from nexora.nke.safety import Executor, SafetyController, SafetyViolation


def make_fake_proc(tmp: Path) -> Path:
    proc = tmp / "proc"
    (proc / "pressure").mkdir(parents=True)
    (proc / "pressure" / "cpu").write_text("some avg10=0.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
    (proc / "pressure" / "memory").write_text("some avg10=0.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
    (proc / "pressure" / "io").write_text("some avg10=0.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
    (proc / "meminfo").write_text(
        "MemTotal:       16000000 kB\nMemAvailable:    8000000 kB\n"
        "SwapTotal:       2000000 kB\nSwapFree:        1900000 kB\n"
    )
    (proc / "loadavg").write_text("0.10 0.20 0.30 1/100 1234\n")
    (proc / "swaps").write_text("Filename\t\t\t\tType\t\tSize\tUsed\tPriority\n/swapfile file 2097148 0 -2\n")
    (proc / "sys" / "kernel").mkdir(parents=True)
    (proc / "sys" / "kernel" / "tainted").write_text("0\n")
    (proc / "1").mkdir()
    (proc / "1" / "comm").write_text("systemd\n")
    (proc / "1" / "stat").write_text("1 (systemd) S 0 1 1 0 -1 4194560 1 1 0 0 500 100 0 0 20 0 1 0\n")
    return proc


def make_fake_sys(tmp: Path, with_cgroup: bool = True, with_cpufreq: bool = True) -> Path:
    sysfs = tmp / "sys"
    (sysfs / "class" / "net").mkdir(parents=True)
    (sysfs / "class" / "net" / "wlan0").mkdir()
    if with_cgroup:
        (sysfs / "fs" / "cgroup").mkdir(parents=True)
        (sysfs / "fs" / "cgroup" / "cgroup.controllers").write_text("cpu io memory pids\n")
    if with_cpufreq:
        cpu0 = sysfs / "devices" / "system" / "cpu" / "cpu0" / "cpufreq"
        cpu0.mkdir(parents=True)
        (cpu0 / "scaling_available_governors").write_text("performance powersave schedutil\n")
        (cpu0 / "scaling_governor").write_text("schedutil\n")
    return sysfs


class FakeExecutor(Executor):
    def __init__(self):
        self.writes, self.mkdirs, self.renices, self.signals = [], [], [], []

    def write_sys(self, path, data):
        self.writes.append((path, data))

    def mkdir(self, path):
        self.mkdirs.append(path)

    def renice(self, pid, nice):
        self.renices.append((pid, nice))

    def signal(self, pid, sig):
        self.signals.append((pid, sig))


class CapabilitiesTests(unittest.TestCase):
    def test_deteccion_con_procsys_falsos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            caps = detect_capabilities(str(make_fake_proc(root)), str(make_fake_sys(root)), kernel_release="6.9.0")
        self.assertEqual(caps["kernel_release"], "6.9.0")
        self.assertTrue(caps["psi"]["cpu"] is not None)
        self.assertTrue(caps["cgroup_v2"]["available"])
        self.assertIn("memory", caps["cgroup_v2"]["controllers"])
        self.assertTrue(caps["can_cgroup_limits"])
        self.assertTrue(caps["can_cpufreq_tuning"])
        self.assertTrue(caps["can_psi_monitoring"])
        self.assertEqual(caps["swap"]["devices"][0]["path"], "/swapfile")

    def test_sin_psi_ni_cgroups_se_declara_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "proc").mkdir()
            (root / "sys").mkdir()
            caps = detect_capabilities(str(root / "proc"), str(root / "sys"), kernel_release="x")
        self.assertFalse(caps["can_psi_monitoring"])
        self.assertFalse(caps["cgroup_v2"]["available"])
        self.assertFalse(caps["can_cgroup_limits"])
        self.assertIsNone(caps["psi"]["cpu"])

    def test_sistema_real_sin_explotar(self):
        caps = detect_capabilities(kernel_release="test")
        self.assertIn("kernel_release", caps)
        self.assertIsInstance(caps["swap"]["devices"], list)


class MonitorTests(unittest.TestCase):
    def test_meminfo_y_procesos(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = make_fake_proc(Path(tmp))
            mem = read_meminfo(proc)
            self.assertEqual(mem["MemTotal_mb"], 15625.0)
            self.assertEqual(mem["SwapFree_mb"], 1855.5)
            tops = top_processes(proc)
            self.assertEqual(tops[0]["pid"], 1)
            self.assertEqual(tops[0]["cpu_ticks"], 600)

    def test_sondeo_adaptativo_en_reposo(self):
        with tempfile.TemporaryDirectory() as tmp:
            mon = NKMonitor(str(make_fake_proc(Path(tmp))))
            self.assertEqual(mon.interval, 2.0)
            mon.sample()
            self.assertEqual(mon.interval, 4.0)   # reposo: se duplica
            mon.sample()
            self.assertEqual(mon.interval, 8.0)

    def test_presion_vuelve_al_intervalo_minimo(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = make_fake_proc(Path(tmp))
            mon = NKMonitor(str(proc))
            mon.sample()
            mon.sample()
            self.assertGreater(mon.interval, 2.0)
            (proc / "pressure" / "cpu").write_text("some avg10=80.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
            mon.sample()
            self.assertEqual(mon.interval, 2.0)


class AnalyzerTests(unittest.TestCase):
    def _sample(self, **over):
        base = {
            "psi": {"cpu": {"some": 0.0}, "memory": {"some": 0.0}, "io": {"some": 0.0}},
            "mem": {"MemAvailable_mb": 8000.0, "MemTotal_mb": 15625.0, "SwapFree_mb": 1855.5, "SwapTotal_mb": 2000.0},
            "load": (0.2, 0.3, 0.4),
            "top_processes": [],
        }
        base.update(over)
        return base

    def test_sistema_sano_sin_hallazgos(self):
        self.assertEqual(analyze(self._sample()), [])

    def test_presion_de_memoria_critica(self):
        f = analyze(self._sample(psi={"memory": {"some": 65.0}, "cpu": {"some": 0.0}, "io": {"some": 0.0}}))
        self.assertTrue(any(x["kind"] == "memory_pressure" and x["severity"] == "critical" for x in f))

    def test_thrashing_de_swap(self):
        f = analyze(self._sample(
            psi={"memory": {"some": 40.0}, "cpu": {"some": 0.0}, "io": {"some": 0.0}},
            mem={"MemAvailable_mb": 300.0, "MemTotal_mb": 15625.0, "SwapFree_mb": 100.0, "SwapTotal_mb": 2000.0},
        ))
        kinds = {x["kind"] for x in f}
        self.assertIn("swap_thrashing", kinds)
        self.assertIn("low_mem_available", kinds)

    def test_presion_de_cpu_y_io(self):
        f = analyze(self._sample(psi={"cpu": {"some": 50.0}, "memory": {"some": 0.0}, "io": {"some": 35.0}}))
        kinds = {x["kind"] for x in f}
        self.assertIn("cpu_pressure", kinds)
        self.assertIn("io_pressure", kinds)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.caps = detect_capabilities(str(make_fake_proc(root)), str(make_fake_sys(root)), kernel_release="t")
        self.pe = PolicyEngine(self.caps)

    def test_categorias_del_catalogo(self):
        self.assertEqual(ACTION_CATALOG["renice_agent"]["category"], CATEGORY_A)
        self.assertEqual(ACTION_CATALOG["set_governor"]["category"], CATEGORY_B)
        self.assertEqual(ACTION_CATALOG["load_kernel_module"]["category"], CATEGORY_C)

    def test_presion_memoria_genera_acciones_automaticas(self):
        findings = [{"kind": "memory_pressure", "severity": "critical", "detail": "x",
                     "suggests": ["reduce_agent_ram", "pause_secondary_agents"]}]
        d = self.pe.decide(findings)
        kinds = [a.kind for a in d[CATEGORY_A]]
        self.assertIn("reduce_agent_ram", kinds)
        self.assertIn("pause_secondary_agents", [a.kind for a in d[CATEGORY_B]])

    def test_capacidad_ausente_no_genera_accion(self):
        self.pe.caps["can_cgroup_limits"] = False
        findings = [{"kind": "memory_pressure", "severity": "warning", "detail": "x",
                     "suggests": ["reduce_agent_ram"]}]
        d = self.pe.decide(findings)
        self.assertEqual(d[CATEGORY_A], [])

    def test_carga_de_modulo_es_propuesta_protegida(self):
        findings = [{"kind": "x", "severity": "info", "detail": "y", "suggests": ["load_kernel_module"]}]
        d = self.pe.decide(findings)
        self.assertEqual([a.kind for a in d[CATEGORY_C]], ["load_kernel_module"])
        self.assertEqual([a for a in d[CATEGORY_A]], [])

    def test_deduplicacion(self):
        findings = [
            {"kind": "memory_pressure", "severity": "warning", "detail": "a", "suggests": ["reduce_agent_ram"]},
            {"kind": "low_mem_available", "severity": "warning", "detail": "b", "suggests": ["reduce_agent_ram"]},
        ]
        d = self.pe.decide(findings)
        self.assertEqual(len(d[CATEGORY_A]), 1)


class SafetyTests(unittest.TestCase):
    def test_categoria_c_nunca_se_aplica(self):
        sc = SafetyController(executor=FakeExecutor())
        from nexora.nke.policy import Action
        action = Action("load_kernel_module", CATEGORY_C, False, "ext4", {}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action)
        self.assertEqual(FakeExecutor().writes, [])

    def test_categoria_b_exige_aprobacion(self):
        sc = SafetyController(executor=FakeExecutor())
        from nexora.nke.policy import Action
        action = Action("set_governor", CATEGORY_B, True, "cpu0", {"governor": "performance"}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action, user_approved=False)

    def test_accion_a_se_aplica_y_se_revierte(self):
        fx = FakeExecutor()
        sc = SafetyController(executor=fx)
        from nexora.nke.policy import Action
        action = Action("renice_agent", CATEGORY_A, True, "1234", {"nice": 10}, "presión de CPU")
        outcome = sc.apply(action)
        self.assertEqual(fx.renices, [(1234, 10)])
        sc.rollback(outcome["rollback"])
        self.assertEqual(fx.renices[-1], (1234, 0))

    def test_cgroup_limit_real_con_ejecutor(self):
        fx = FakeExecutor()
        sc = SafetyController(executor=fx, cgroup_base="/sys/fs/cgroup")
        from nexora.nke.policy import Action
        action = Action("cgroup_limit", CATEGORY_A, True, "nexora.slice",
                        {"memory.max": "2G", "cpu.max": "200000 100000"}, "límite de agentes")
        sc.apply(action)
        self.assertIn("/sys/fs/cgroup/nexora.slice", fx.mkdirs)
        self.assertIn(("/sys/fs/cgroup/nexora.slice/memory.max", "2G"), fx.writes)


class EngineTests(unittest.TestCase):
    def _engine(self, tmp, psi_memory="0.00"):
        proc = make_fake_proc(Path(tmp))
        (proc / "pressure" / "memory").write_text(
            f"some avg10={psi_memory} avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
        sysfs = make_fake_sys(Path(tmp))

        class FakeMonitor(NKMonitor):
            def capabilities(self):
                return detect_capabilities(str(proc), str(sysfs), kernel_release="t")

        t = {"now": 0.0}
        engine = NKEngine(monitor=FakeMonitor(str(proc)), executor=FakeExecutor(),
                          clock=lambda: t["now"], sleeper=lambda s: t.__setitem__("now", t["now"] + s))
        return engine, proc

    def test_ciclo_sano_no_aplica_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._engine(tmp)
            cycle = engine.run_cycle()
            self.assertEqual(cycle["applied"], [])
            self.assertEqual(cycle["findings"], [])

    def test_presion_memoria_aplica_acciones_con_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, proc = self._engine(tmp, psi_memory="50.00")
            c1 = engine.run_cycle()
            self.assertGreater(len(c1["applied"]), 0)
            self.assertLessEqual(len(c1["applied"]), 3)
            # Cooldown: el ciclo inmediatamente siguiente no repite acciones.
            c2 = engine.run_cycle()
            self.assertEqual(c2["applied"], [])

    def test_degradacion_provoca_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, proc = self._engine(tmp, psi_memory="50.00")

            # Tras el primer muestreo, la presión empeora: el motor debe revertir.
            original_sample = engine.monitor.sample
            calls = {"n": 0}
            def sample():
                calls["n"] += 1
                s = original_sample()
                if calls["n"] >= 2:  # muestreo post-aplicación (2.º muestreo del ciclo)
                    (proc / "pressure" / "memory").write_text("some avg10=90.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
                return s
            engine.monitor.sample = sample
            cycle = engine.run_cycle()
            self.assertTrue(cycle["rolled_back"])
            self.assertIsNotNone(engine.history.last_rollback())

    def test_huella_propia_medido(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._engine(tmp)
            cycle = engine.run_cycle()
            self.assertIn("duration_ms", cycle)
            self.assertGreaterEqual(cycle["duration_ms"], 0.0)

    def test_bucle_con_limite_de_ciclos(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._engine(tmp)
            engine.loop(max_cycles=2)
            self.assertEqual(engine.status()["cycles"], 2)


class HistoryTests(unittest.TestCase):
    def test_registro_acotado_y_resumen(self):
        h = NKEHistory(size=3)
        for i in range(5):
            h.record("apply", f"e{i}")
        self.assertEqual(len(h.events()), 3)
        self.assertEqual(h.summary(), {"apply": 3})
        h.record("rollback", "r")
        self.assertIsNotNone(h.last_rollback())


class KernelExtensionTests(unittest.TestCase):
    def test_estado_del_kernel_sin_privilegios(self):
        from nexora.nke.kernel_extension import KernelManager
        st = KernelManager(release="6.9.0-test").status()
        self.assertEqual(st["release"], "6.9.0-test")
        self.assertIn("cgroup_v2", st)

    def test_modulos_cargados_solo_lectura(self):
        from nexora.nke.kernel_extension import ModuleManager
        with tempfile.TemporaryDirectory() as tmp:
            proc = make_fake_proc(Path(tmp))
            (proc / "modules").write_text("ext4 903112 1 - Live 0x0000000000000000\n")
            mods = ModuleManager(str(proc)).loaded()
            self.assertEqual(mods[0]["name"], "ext4")

    def test_propuesta_de_modulo_nunca_se_ejecuta(self):
        from nexora.nke.kernel_extension import ModuleManager
        p = ModuleManager().propose_load("btrfs", "sistema de archivos solicitado")
        self.assertEqual(p["category"], "protected")
        self.assertFalse(p["executed_by_nke"])
        with self.assertRaises(ValueError):
            ModuleManager().propose_load("rm -rf /", "malo")

    def test_api_de_extension_lista_cerrada(self):
        from nexora.nke.kernel_extension import ExtensionAPI
        api = ExtensionAPI()
        self.assertEqual(api.request("forge", "consulta_inventada")["status"], "denied")
        res = api.request("forge", "kernel_status")
        self.assertEqual(res["status"], "ok")

    def test_diagnostico_de_controladores(self):
        from nexora.nke.kernel_extension import KernelWatchdog
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sysfs = root / "sys"
            (sysfs / "class").mkdir(parents=True)   # sin net ni drm
            diag = KernelWatchdog(str(make_fake_proc(root)), str(sysfs)).diagnose()
            self.assertTrue(any("red" in i for i in diag["issues"]))


class IntegrationTests(unittest.TestCase):
    def test_cli_nke_status_y_history(self):
        import contextlib
        import io
        from nexora.cli import main
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["nke", "status"])
        self.assertEqual(code, 0)
        self.assertIn("Nexora Kernel Engine", out.getvalue())
        out2 = io.StringIO()
        with contextlib.redirect_stdout(out2):
            code2 = main(["nke", "history"])
        self.assertEqual(code2, 0)

    def test_dashboard_expone_panel_kernel_engine(self):
        from nexora.ui.dashboard import NexoraDashboard
        dash = NexoraDashboard()
        ke = dash.widgets["kernel_engine"]
        if ke is not None:
            self.assertIn("release", ke)
            self.assertIn("cgroup_v2", ke)
        text = dash.render_text()
        self.assertIn("Kernel Engine", text)


if __name__ == "__main__":
    unittest.main()
