"""Tests de NKE: capacidades, monitor, analizador, políticas, seguridad, motor y extensión de kernel.

Incluye regresión del ciclo de rollback: rollback acotado al ciclo actual,
restauración exacta de valores previos, fallos parciales y acciones sin
implementación cerradas con motivo explícito.
"""

import os
import tempfile
import unittest
from pathlib import Path

from nexora.nke.analyzer import analyze
from nexora.nke.capabilities import detect_capabilities
from nexora.nke.engine import NKEngine
from nexora.nke.history import NKEHistory
from nexora.nke.monitor import NKMonitor, read_meminfo, top_processes
from nexora.nke.policy import CATEGORY_A, CATEGORY_B, CATEGORY_C, ACTION_CATALOG, Action, PolicyEngine
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
    (proc / "sys" / "vm").mkdir(parents=True)
    (proc / "sys" / "vm" / "swappiness").write_text("60\n")
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
    """Ejecutor falso con estado simulado: archivos, nice y fallos inyectables."""

    def __init__(self):
        self.writes, self.mkdirs, self.renices, self.signals = [], [], [], []
        self.files = {}       # path -> contenido actual simulado
        self.nice = {}        # pid -> nice actual simulado
        self.fail_writes = set()
        self.fail_renices = False

    def write_sys(self, path, data):
        if path in self.fail_writes:
            raise OSError(f"escritura denegada en {path}")
        self.writes.append((path, data))
        self.files[path] = data

    def read_sys(self, path):
        return self.files.get(path)

    def mkdir(self, path):
        self.mkdirs.append(path)

    def renice(self, pid, nice):
        if self.fail_renices:
            raise OSError("renice denegado")
        self.renices.append((pid, nice))
        self.nice[pid] = nice

    def getnice(self, pid):
        return self.nice.get(pid, 0)

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

    def test_presion_de_memoria_propone_limite_derivado_de_memtotal(self):
        f = analyze(self._sample(psi={"memory": {"some": 65.0}, "cpu": {"some": 0.0}, "io": {"some": 0.0}}))
        mp = next(x for x in f if x["kind"] == "memory_pressure")
        self.assertEqual(mp["params"]["memory.max"], "3.8G")   # 25% de 15625 MB

    def test_presion_de_cpu_adjunta_procesos_top(self):
        """El hallazgo de CPU incluye los procesos top: deprioritize necesita un pid real."""
        tops = [{"pid": 7, "comm": "juego", "cpu_ticks": 900}]
        f = analyze(self._sample(psi={"cpu": {"some": 50.0}, "memory": {"some": 0.0}, "io": {"some": 0.0}},
                                 top_processes=tops))
        cp = next(x for x in f if x["kind"] == "cpu_pressure")
        self.assertEqual(cp["top_processes"], tops)

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

    def test_toda_accion_declara_su_implementacion(self):
        for kind, spec in ACTION_CATALOG.items():
            self.assertIn("implemented", spec, f"{kind} sin declaración de implementación")

    def test_presion_memoria_genera_acciones_automaticas(self):
        findings = [{"kind": "memory_pressure", "severity": "critical", "detail": "x",
                     "params": {"memory.max": "2G"},
                     "suggests": ["reduce_agent_ram", "pause_secondary_agents"]}]
        d = self.pe.decide(findings)
        kinds = [a.kind for a in d[CATEGORY_A]]
        self.assertIn("reduce_agent_ram", kinds)
        self.assertIn("pause_secondary_agents", [a.kind for a in d[CATEGORY_B]])

    def test_limite_sin_parametros_no_se_propone(self):
        """Un límite de cgroup sin parámetros sería una aplicación vacía: no se propone."""
        findings = [{"kind": "memory_pressure", "severity": "warning", "detail": "x",
                     "suggests": ["reduce_agent_ram"]}]
        d = self.pe.decide(findings)
        self.assertEqual(d[CATEGORY_A], [])

    def test_cambiar_dns_no_se_propone_por_no_estar_implementada(self):
        findings = [{"kind": "dns_lento", "severity": "info", "detail": "x",
                     "suggests": ["change_dns"]}]
        d = self.pe.decide(findings)
        self.assertEqual(d[CATEGORY_B], [])
        self.assertEqual(d[CATEGORY_A], [])

    def test_carga_de_modulo_no_se_propone_por_no_estar_implementada(self):
        """Cargar módulos del kernel es privilegiado y sin implementación: nunca se propone."""
        findings = [{"kind": "x", "severity": "info", "detail": "y", "suggests": ["load_kernel_module"]}]
        d = self.pe.decide(findings)
        self.assertEqual([a.kind for a in d[CATEGORY_C]], [])
        self.assertEqual([a for a in d[CATEGORY_A]], [])
        self.assertEqual([a for a in d[CATEGORY_B]], [])
        self.assertFalse(ACTION_CATALOG["load_kernel_module"]["implemented"])
        self.assertEqual(ACTION_CATALOG["load_kernel_module"]["category"], CATEGORY_C)

    def test_deprioritize_sin_pid_real_no_se_propone(self):
        """Sin procesos top en el hallazgo no hay pid: no se renicea un objetivo simbólico."""
        findings = [{"kind": "cpu_pressure", "severity": "warning", "detail": "x",
                     "suggests": ["deprioritize_secondary"]}]
        d = self.pe.decide(findings)
        self.assertEqual(d[CATEGORY_A], [])

    def test_deprioritize_con_pid_real_se_propone(self):
        findings = [{"kind": "cpu_pressure", "severity": "warning", "detail": "x",
                     "top_processes": [{"pid": 7, "comm": "juego", "cpu_ticks": 900}],
                     "suggests": ["deprioritize_secondary"]}]
        d = self.pe.decide(findings)
        self.assertEqual([a.kind for a in d[CATEGORY_A]], ["deprioritize_secondary"])
        self.assertEqual(d[CATEGORY_A][0].target, "7")

    def test_peticion_de_perfil_prevalece_sobre_hallazgo(self):
        """La petición de perfil aporta los pids: la deduplicación conserva sus parámetros."""
        findings = [{"kind": "memory_pressure", "severity": "warning", "detail": "x",
                     "params": {"memory.max": "2G"},
                     "suggests": ["pause_secondary_agents"]}]
        reqs = [{"kind": "pause_secondary_agents", "mode": "gaming", "params": {"pids": [4242]}}]
        d = self.pe.decide(findings, reqs)
        pausas = [a for a in d[CATEGORY_B] if a.kind == "pause_secondary_agents"]
        self.assertEqual(len(pausas), 1)
        self.assertEqual(pausas[0].params.get("pids"), [4242])

    def test_capacidad_ausente_no_genera_accion(self):
        self.pe.caps["can_cgroup_limits"] = False
        findings = [{"kind": "memory_pressure", "severity": "warning", "detail": "x",
                     "params": {"memory.max": "2G"},
                     "suggests": ["reduce_agent_ram"]}]
        d = self.pe.decide(findings)
        self.assertEqual(d[CATEGORY_A], [])

    def test_deduplicacion(self):
        findings = [
            {"kind": "memory_pressure", "severity": "warning", "detail": "a",
             "params": {"memory.max": "2G"}, "suggests": ["reduce_agent_ram"]},
            {"kind": "low_mem_available", "severity": "warning", "detail": "b",
             "params": {"memory.max": "2G"}, "suggests": ["reduce_agent_ram"]},
        ]
        d = self.pe.decide(findings)
        self.assertEqual(len(d[CATEGORY_A]), 1)


class SafetyTests(unittest.TestCase):
    def test_categoria_c_nunca_se_aplica(self):
        sc = SafetyController(executor=FakeExecutor())
        action = Action("load_kernel_module", CATEGORY_C, False, "ext4", {}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action)
        self.assertEqual(FakeExecutor().writes, [])

    def test_categoria_b_exige_aprobacion(self):
        sc = SafetyController(executor=FakeExecutor())
        action = Action("set_governor", CATEGORY_B, True, "cpu0", {"governor": "performance"}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action, user_approved=False)

    def test_accion_a_se_aplica_y_se_revierte(self):
        fx = FakeExecutor()
        sc = SafetyController(executor=fx)
        action = Action("renice_agent", CATEGORY_A, True, "1234", {"nice": 10}, "presión de CPU")
        outcome = sc.apply(action)
        self.assertEqual(fx.renices, [(1234, 10)])
        sc.rollback(outcome["rollback"])
        self.assertEqual(fx.renices[-1], (1234, 0))

    def test_restauracion_exacta_del_nice_previo(self):
        """El rollback restaura el nice real previo, no el 0 por defecto."""
        fx = FakeExecutor()
        fx.nice[1234] = 5
        sc = SafetyController(executor=fx)
        action = Action("renice_agent", CATEGORY_A, True, "1234", {"nice": 10}, "presión de CPU")
        outcome = sc.apply(action)
        self.assertEqual(fx.renices[-1], (1234, 10))
        sc.rollback(outcome["rollback"])
        self.assertEqual(fx.renices[-1], (1234, 5))

    def test_renice_sin_nice_previo_legible_no_modifica(self):
        class NoReadExecutor(FakeExecutor):
            def getnice(self, pid):
                return None
        fx = NoReadExecutor()
        sc = SafetyController(executor=fx)
        action = Action("renice_agent", CATEGORY_A, True, "1234", {"nice": 10}, "presión de CPU")
        with self.assertRaises(SafetyViolation):
            sc.apply(action)
        self.assertEqual(fx.renices, [])

    def test_renice_con_objetivo_no_numerico_se_rechaza(self):
        fx = FakeExecutor()
        sc = SafetyController(executor=fx)
        action = Action("deprioritize_secondary", CATEGORY_A, True, "agentes-nexora", {"nice": 10}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action)
        self.assertEqual(fx.renices, [])

    def test_cgroup_limit_real_con_ejecutor(self):
        fx = FakeExecutor()
        sc = SafetyController(executor=fx, cgroup_base="/sys/fs/cgroup")
        action = Action("cgroup_limit", CATEGORY_A, True, "nexora.slice",
                        {"memory.max": "2G", "cpu.max": "200000 100000"}, "límite de agentes")
        sc.apply(action)
        self.assertIn("/sys/fs/cgroup/nexora.slice", fx.mkdirs)
        self.assertIn(("/sys/fs/cgroup/nexora.slice/memory.max", "2G"), fx.writes)

    def test_cgroup_restaura_el_valor_previo_real(self):
        """No se asume "max": si el límite previo era 4G, se restaura 4G."""
        fx = FakeExecutor()
        fx.files["/sys/fs/cgroup/nexora.slice/memory.max"] = "4G"
        sc = SafetyController(executor=fx)
        action = Action("cgroup_limit", CATEGORY_A, True, "nexora.slice", {"memory.max": "2G"}, "límite")
        outcome = sc.apply(action)
        sc.rollback(outcome["rollback"])
        self.assertIn(("/sys/fs/cgroup/nexora.slice/memory.max", "4G"), fx.writes)

    def test_cgroup_nuevo_slice_restaura_el_defecto_del_kernel(self):
        """Un slice recién creado no tenía límite: el defecto del kernel es "max"."""
        fx = FakeExecutor()
        sc = SafetyController(executor=fx)
        action = Action("cgroup_limit", CATEGORY_A, True, "nexora.slice", {"memory.max": "2G"}, "límite")
        outcome = sc.apply(action)
        sc.rollback(outcome["rollback"])
        self.assertIn(("/sys/fs/cgroup/nexora.slice/memory.max", "max"), fx.writes)

    def test_cgroup_sin_parametros_se_rechaza_sin_efectos(self):
        fx = FakeExecutor()
        sc = SafetyController(executor=fx)
        action = Action("reduce_agent_ram", CATEGORY_A, True, "nexora.slice", {}, "límite vacío")
        with self.assertRaises(SafetyViolation):
            sc.apply(action)
        self.assertEqual(fx.writes, [])
        self.assertEqual(fx.mkdirs, [])   # ni siquiera se crea el slice

    def test_governor_restaura_el_previo_real(self):
        """No se asume "schedutil": se restaura el gobernador que había."""
        fx = FakeExecutor()
        gov = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        fx.files[gov] = "powersave"
        sc = SafetyController(executor=fx)
        action = Action("set_governor", CATEGORY_B, True, "cpu0", {"governor": "performance"}, "prueba")
        outcome = sc.apply(action, user_approved=True)
        self.assertEqual(fx.files[gov], "performance")
        sc.rollback(outcome["rollback"])
        self.assertEqual(fx.files[gov], "powersave")

    def test_governor_sin_valor_previo_legible_no_modifica(self):
        fx = FakeExecutor()   # sin gobernador previo en files
        sc = SafetyController(executor=fx)
        action = Action("set_governor", CATEGORY_B, True, "cpu0", {"governor": "performance"}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action, user_approved=True)
        self.assertEqual(fx.writes, [])

    def test_set_swappiness_aplica_y_restaura(self):
        fx = FakeExecutor()
        fx.files["/proc/sys/vm/swappiness"] = "60"
        sc = SafetyController(executor=fx)
        action = Action("set_swappiness", CATEGORY_B, True, "vm.swappiness", {"swappiness": 10}, "prueba")
        outcome = sc.apply(action, user_approved=True)
        self.assertEqual(fx.files["/proc/sys/vm/swappiness"], "10")
        sc.rollback(outcome["rollback"])
        self.assertEqual(fx.files["/proc/sys/vm/swappiness"], "60")

    def test_set_swappiness_fuera_de_rango_se_rechaza(self):
        fx = FakeExecutor()
        fx.files["/proc/sys/vm/swappiness"] = "60"
        sc = SafetyController(executor=fx)
        action = Action("set_swappiness", CATEGORY_B, True, "vm.swappiness", {"swappiness": 500}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action, user_approved=True)
        self.assertEqual(fx.files["/proc/sys/vm/swappiness"], "60")

    def test_change_dns_no_implementada_se_rechaza_con_motivo(self):
        """El catálogo la declara, pero no existe implementación segura: nunca se ejecuta."""
        sc = SafetyController(executor=FakeExecutor())
        action = Action("change_dns", CATEGORY_B, True, "sistema", {"servers": ["1.1.1.1"]}, "prueba")
        with self.assertRaises(SafetyViolation) as ctx:
            sc.apply(action, user_approved=True)
        self.assertIn("sin implementación", str(ctx.exception))

    def test_accion_desconocida_se_rechaza(self):
        sc = SafetyController(executor=FakeExecutor())
        action = Action("ajuste_inventado", CATEGORY_A, True, "x", {}, "prueba")
        with self.assertRaises(SafetyViolation):
            sc.apply(action)

    def test_rollback_desconocido_lanza_error(self):
        sc = SafetyController(executor=FakeExecutor())
        with self.assertRaises(ValueError):
            sc.rollback({"kind": "restore_inexistente"})

    def test_rollback_verifica_la_restauracion(self):
        fx = FakeExecutor()
        gov = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        fx.files[gov] = "powersave"
        sc = SafetyController(executor=fx)
        action = Action("set_governor", CATEGORY_B, True, "cpu0", {"governor": "performance"}, "prueba")
        outcome = sc.apply(action, user_approved=True)
        fx.fail_writes.add(gov)   # la restauración fallará al reescribir
        with self.assertRaises(OSError):
            sc.rollback(outcome["rollback"])


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
            self.assertTrue(all("modification" in a for a in c1["applied"]))
            # Cooldown: el ciclo inmediatamente siguiente no repite acciones.
            c2 = engine.run_cycle()
            self.assertEqual(c2["applied"], [])

    def test_degradacion_provoca_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, proc = self._engine(tmp, psi_memory="50.00")

            # A partir del segundo muestreo (el posterior a la aplicación), la
            # presión de memoria empeora: el motor debe revertir lo aplicado.
            original_sample = engine.monitor.sample
            calls = {"n": 0}
            def sample():
                calls["n"] += 1
                if calls["n"] >= 2:
                    (proc / "pressure" / "memory").write_text(
                        "some avg10=90.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
                return original_sample()
            engine.monitor.sample = sample
            cycle = engine.run_cycle()
            self.assertEqual(cycle["rolled_back"], ["reduce_agent_ram"])
            self.assertIsNotNone(engine.history.last_rollback())
            states = {m["state"] for m in engine.modifications()}
            self.assertEqual(states, {"reverted"})

    def test_rollback_no_toca_ciclos_anteriores(self):
        """Regresión del bug crítico: la degradación del ciclo 2 solo revierte el ciclo 2."""
        with tempfile.TemporaryDirectory() as tmp:
            engine, proc = self._engine(tmp, psi_memory="50.00")
            c1 = engine.run_cycle()   # aplica reduce_agent_ram (ciclo 1)
            self.assertTrue(c1["applied"])
            # Ciclo 2: presión de CPU (acción distinta) y degradación posterior.
            (proc / "pressure" / "memory").write_text("some avg10=0.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
            (proc / "pressure" / "cpu").write_text("some avg10=80.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
            original_sample = engine.monitor.sample
            calls = {"n": 0}
            def sample():
                calls["n"] += 1
                if calls["n"] == 2:
                    (proc / "pressure" / "memory").write_text(
                        "some avg10=90.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
                return original_sample()
            engine.monitor.sample = sample
            c2 = engine.run_cycle()
            self.assertEqual([a["kind"] for a in c2["applied"]], ["deprioritize_secondary"])
            self.assertEqual(c2["rolled_back"], ["deprioritize_secondary"])
            mods = engine.modifications()
            self.assertTrue(all(m["state"] == "applied" for m in mods if m["cycle"] == 1))
            self.assertTrue(all(m["state"] == "reverted" for m in mods if m["cycle"] == 2))
            # El ajuste del ciclo 1 sigue activo y undo_last lo revierte a él.
            out = engine.undo_last()
            self.assertEqual(out["rolled_back"]["cycle"], 1)
            self.assertEqual(out["rolled_back"]["kind"], "reduce_agent_ram")
            self.assertTrue(all(m["state"] == "reverted" for m in engine.modifications()))

    def test_fallo_parcial_de_rollback_deja_estado_consistente(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, proc = self._engine(tmp, psi_memory="50.00")
            (proc / "pressure" / "cpu").write_text("some avg10=80.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
            real_rollback = engine.safety.rollback
            armed = {"on": True}
            def rollback(rb):
                if armed["on"] and rb.get("kind") == "restore_nice":
                    armed["on"] = False
                    raise OSError("fallo de restauración inyectado")
                return real_rollback(rb)
            engine.safety.rollback = rollback
            original_sample = engine.monitor.sample
            calls = {"n": 0}
            def sample():
                calls["n"] += 1
                if calls["n"] == 2:
                    (proc / "pressure" / "memory").write_text(
                        "some avg10=90.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
                return original_sample()
            engine.monitor.sample = sample
            cycle = engine.run_cycle()   # no debe lanzar aunque un rollback falle
            self.assertEqual(len(cycle["applied"]), 2)
            self.assertEqual(cycle["rolled_back"], ["reduce_agent_ram"])
            states = {m["kind"]: m["state"] for m in engine.modifications()}
            self.assertEqual(states["reduce_agent_ram"], "reverted")
            self.assertEqual(states["deprioritize_secondary"], "failed")
            self.assertTrue(engine.history.events("error"))

    def test_propuesta_aprobada_queda_registrada_y_deshacible(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._engine(tmp, psi_memory="50.00")
            engine.profile_requests = [{"kind": "pause_secondary_agents", "mode": "gaming",
                                        "params": {"pids": [4242]}}]
            engine.run_cycle()
            self.assertTrue(any(a.kind == "pause_secondary_agents" for a in engine.last_supervised()))
            out = engine.approve_proposal("pause_secondary_agents", "sistema")
            self.assertTrue(out["applied"])
            mods = engine.modifications()
            self.assertEqual(len(mods), 2)   # reduce_agent_ram (A) + pause (B aprobada)
            self.assertTrue(all(m["state"] == "applied" for m in mods))
            engine.undo_last()
            self.assertEqual(engine.modifications()[-1]["state"], "reverted")
            self.assertIn((4242, 19), engine.safety.exec.signals)
            self.assertIn((4242, 18), engine.safety.exec.signals)

    def test_estado_expone_modificaciones(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._engine(tmp, psi_memory="50.00")
            engine.run_cycle()
            st = engine.status()
            self.assertEqual(st["modifications"]["by_state"].get("applied"), 1)
            self.assertEqual(st["modifications"]["recent"][0]["kind"], "reduce_agent_ram")

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
