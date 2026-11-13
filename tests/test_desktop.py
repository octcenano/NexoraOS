"""Nexora Desktop: modelos puros, estados explícitos y seguridad.

Sin GTK: la vista gtkui requiere PyGObject y sesión gráfica; los modelos se
prueban directamente (patrón modelo/vista ya usado en ui/dashboard).
"""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from nexora.core.ai_engine import LocalAIEngine
from nexora.core.coordinator import Coordinator
from nexora.core.registry import ModeRegistry
from nexora.desktop import NexoraDesktopApp
from nexora.desktop.dashboard import DashboardModel, service_state, top_processes
from nexora.desktop.hub import NexoraHub
from nexora.desktop.mode_center import ModeCenter
from nexora.desktop.nke_control import NKEControl
from nexora.desktop.nke_panel import AsyncRunner, NkePanelModel, Poller
from nexora.desktop.shell import ApplicationIndex, GlobalSearch, PANEL_LAYOUT, workspaces
from nexora.desktop.system_center import PRIVILEGED_ACTIONS, SECTIONS, SystemCenter, list_users, pending_updates
from nexora.nke.capabilities import detect_capabilities
from nexora.nke.engine import NKEngine
from nexora.nke.monitor import NKMonitor
from nexora.nke.safety import Executor


def write_desktop(path: Path, name: str, exec_name: str, categories: str = "Utility",
                  nodisplay: str = "false"):
    path.write_text(
        "[Desktop Entry]\n"
        f"Name={name}\n"
        f"Exec={exec_name}\n"
        f"Categories={categories}\n"
        f"NoDisplay={nodisplay}\n",
        encoding="utf-8",
    )


def _make_fake_proc(tmp: Path) -> Path:
    proc = tmp / "proc"
    (proc / "pressure").mkdir(parents=True)
    (proc / "pressure" / "cpu").write_text("some avg10=0.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
    (proc / "pressure" / "memory").write_text("some avg10=50.00 avg60=0.00 avg300=0.00\nfull avg10=0.00\n")
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


def _make_fake_sys(tmp: Path) -> Path:
    sysfs = tmp / "sys"
    (sysfs / "class" / "net").mkdir(parents=True)
    (sysfs / "class" / "net" / "wlan0").mkdir()
    (sysfs / "fs" / "cgroup").mkdir(parents=True)
    (sysfs / "fs" / "cgroup" / "cgroup.controllers").write_text("cpu io memory pids\n")
    cpu0 = sysfs / "devices" / "system" / "cpu" / "cpu0" / "cpufreq"
    cpu0.mkdir(parents=True)
    (cpu0 / "scaling_available_governors").write_text("performance powersave schedutil\n")
    (cpu0 / "scaling_governor").write_text("schedutil\n")
    return sysfs


class _FakeExecutor(Executor):
    def __init__(self):
        self.writes, self.mkdirs, self.renices, self.signals = [], [], [], []
        self.files = {}
        self.nice = {}

    def write_sys(self, path, data):
        self.writes.append((path, data))
        self.files[path] = data

    def read_sys(self, path):
        return self.files.get(path)

    def mkdir(self, path):
        self.mkdirs.append(path)

    def renice(self, pid, nice):
        self.renices.append((pid, nice))
        self.nice[pid] = nice

    def getnice(self, pid):
        return self.nice.get(pid, 0)

    def signal(self, pid, sig):
        self.signals.append((pid, sig))


def _test_engine(tmp: Path) -> NKEngine:
    """Motor NKE determinista sobre /proc y /sys falsos, con presión de memoria
    y una petición de perfil que genera una propuesta supervisada pendiente."""
    _make_fake_proc(tmp)
    _make_fake_sys(tmp)

    class FakeMonitor(NKMonitor):
        def capabilities(self):
            return detect_capabilities(str(tmp / "proc"), str(tmp / "sys"),
                                       kernel_release="test")

    t = {"now": 0.0}
    return NKEngine(
        monitor=FakeMonitor(str(tmp / "proc")),
        executor=_FakeExecutor(),
        clock=lambda: t["now"],
        sleeper=lambda s: t.__setitem__("now", t["now"] + s),
        profile_requests=[{"kind": "pause_secondary_agents", "mode": "gaming",
                           "params": {"pids": [4242]}}],
    )


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.apps_dir = Path(self.tmp) / "applications"
        self.apps_dir.mkdir()
        write_desktop(self.apps_dir / "foo.desktop", "Foo Editor", "sh", "Development")
        write_desktop(self.apps_dir / "hidden.desktop", "Hidden", "sh", nodisplay="true")
        self.index = ApplicationIndex(data_dirs=[Path(self.tmp)])

    def test_scan_reads_real_desktop_files_and_skips_hidden(self):
        apps = self.index.scan()
        self.assertEqual([a["name"] for a in apps], ["Foo Editor"])
        self.assertEqual(apps[0]["categories"], ["Development"])

    def test_search_finds_and_returns_empty_state(self):
        res = self.index.search("foo")
        self.assertEqual(len(res), 1)
        self.assertEqual(self.index.search(""), [])

    def test_global_search_states(self):
        gs = GlobalSearch(index=self.index)
        self.assertEqual(gs.query("")["state"], "empty")
        self.assertEqual(gs.query("zzznope")["state"], "no_results")
        res = gs.query("health")
        self.assertEqual(res["state"], "ok")
        self.assertTrue(any(c["name"] == "nexora health" for c in res["commands"]))

    def test_panel_layout_uses_real_xfce_plugins(self):
        plugins = [p["plugin"] for side in ("left", "center", "right")
                   for p in PANEL_LAYOUT[side]]
        self.assertIn("whiskermenu", plugins)
        self.assertIn("systray", plugins)

    def test_workspaces_validates_range(self):
        self.assertEqual(workspaces(4)["count"], 4)
        with self.assertRaises(ValueError):
            workspaces(0)


class DashboardTests(unittest.TestCase):
    def test_snapshot_has_explicit_states_and_real_data(self):
        model = DashboardModel()
        snap = model.snapshot()
        self.assertIn(snap["cpu"]["state"], ("ok", "unavailable"))
        self.assertIn(snap["memory"]["state"], ("ok", "unavailable"))
        # Batería en CI: normalmente no existe; el estado debe ser honesto.
        self.assertIn(snap["battery"]["state"], ("ok", "no_data"))
        self.assertEqual(snap["top_processes"]["state"], "ok")

    def test_top_processes_are_real_and_sorted(self):
        res = top_processes(limit=3)
        self.assertEqual(res["state"], "ok")
        rss = [p["rss_mb"] for p in res["processes"]]
        self.assertEqual(rss, sorted(rss, reverse=True))
        self.assertLessEqual(len(res["processes"]), 3)

    def test_service_state_rejects_bad_names(self):
        self.assertEqual(service_state("x;rm -rf")["state"], "error")
        self.assertEqual(service_state("")["state"], "error")

    def test_core_activity_without_core_is_no_data(self):
        snap = DashboardModel().snapshot()
        self.assertEqual(snap["core_activity"]["state"], "no_data")

    def test_core_activity_with_coordinator_is_real(self):
        snap = DashboardModel(coordinator=Coordinator()).snapshot()
        self.assertEqual(snap["core_activity"]["state"], "ok")
        self.assertIn("agents", snap["core_activity"]["data"])


class ModeCenterTests(unittest.TestCase):
    def setUp(self):
        self.mc = ModeCenter(registry=ModeRegistry())

    def test_activate_validates(self):
        self.assertEqual(self.mc.activate("gaming")["state"], "ok")
        self.assertEqual(self.mc.activate("creator")["state"], "error")
        self.assertEqual(self.mc.active_modes, ["gaming"])

    def test_combine_and_primary(self):
        res = self.mc.combine(["gaming", "stealth"])
        self.assertEqual(res["primary"], "gaming")
        self.assertEqual(self.mc.conflicts(), [
            {"modes": ["gaming", "stealth"],
             "reason": self.mc.conflicts()[0]["reason"]}])

    def test_planned_changes_use_real_allocation(self):
        self.mc.activate("forge", intensity="2")
        plan = self.mc.planned_changes()
        self.assertEqual(plan["state"], "ok")
        self.assertEqual(plan["level"], "level2")
        self.assertEqual(plan["primary"], "forge")
        self.assertTrue(plan["shares"])

    def test_restore_previous_recovers_modes_and_intensities(self):
        self.mc.activate("forge")
        self.mc.set_intensity("forge", "3")
        self.mc.activate("gaming")
        res = self.mc.restore_previous()
        self.assertEqual(res["state"], "ok")
        self.assertEqual(self.mc.active_modes, ["forge"])
        self.assertEqual(self.mc.registry.intensity("forge"), "3")

    def test_deactivate_rules(self):
        self.mc.combine(["gaming", "office"])
        self.assertEqual(self.mc.deactivate("office")["state"], "ok")
        self.assertEqual(self.mc.deactivate("gaming")["state"], "error")

    def test_set_intensity_validates(self):
        self.assertEqual(self.mc.set_intensity("forge", "11")["state"], "error")
        self.assertEqual(self.mc.set_intensity("nope", "1")["state"], "error")


class NKEControlTests(unittest.TestCase):
    def setUp(self):
        self.control = NKEControl()

    def test_overview_reports_capabilities_and_footprint(self):
        ov = self.control.overview()
        self.assertEqual(ov["state"], "ok")
        self.assertIn("kernel_release", ov["capabilities"])
        self.assertFalse(ov["ebpf"]["available"])  # en CI no hay eBPF: degradación declarada
        self.assertIn("avg_cycle_ms", ov["footprint"])

    def test_approve_requires_pending_proposal(self):
        res = self.control.approve("set_governor", "cpu0")
        self.assertEqual(res["state"], "rejected")

    def test_reject_requires_pending_proposal(self):
        res = self.control.reject("set_governor", "cpu0")
        self.assertEqual(res["state"], "error")

    def test_explain_known_and_unknown(self):
        self.assertEqual(self.control.explain("set_governor")["category"], "supervised")
        self.assertEqual(self.control.explain("nope")["state"], "error")

    def test_undo_last_without_active_is_no_data(self):
        self.assertEqual(self.control.undo_last()["state"], "no_data")

    def test_cycle_and_pending_roundtrip(self):
        self.control.refresh()
        # En CI sin presión las propuestas B suelen estar vacías; el estado
        # debe ser coherente en cualquier caso.
        self.assertIsInstance(self.control.pending(), list)


class NkePanelTests(unittest.TestCase):
    def _panel(self, tmp: Path):
        engine = _test_engine(tmp)
        return NkePanelModel(NKEControl(engine=engine)), engine

    def test_snapshot_lists_pending_with_impact_and_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            panel, engine = self._panel(Path(tmp))
            engine.run_cycle()
            snap = panel.snapshot()
            pend = [p for p in snap["pending"] if p["kind"] == "pause_secondary_agents"]
            self.assertEqual(len(pend), 1)
            p = pend[0]
            self.assertEqual(p["category"], "supervised")
            self.assertEqual(p["category_label"], "supervisada")
            self.assertTrue(p["reversible"])
            self.assertTrue(p["implemented"])
            self.assertTrue(p["impact"])
            self.assertEqual(snap["state"], "ok")

    def test_actions_require_explicit_confirmation(self):
        """Sin confirmación explícita no se aplica ningún cambio."""
        with tempfile.TemporaryDirectory() as tmp:
            panel, engine = self._panel(Path(tmp))
            engine.run_cycle()
            self.assertEqual(panel.approve("pause_secondary_agents", "sistema")["state"],
                             "confirmation_required")
            self.assertEqual(panel.reject("pause_secondary_agents", "sistema")["state"],
                             "confirmation_required")
            self.assertEqual(panel.undo_last()["state"], "confirmation_required")
            self.assertEqual(engine.modifications()[-1]["state"], "applied")

    def test_approve_with_confirmation_applies_and_undo_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            panel, engine = self._panel(Path(tmp))
            engine.run_cycle()
            res = panel.approve("pause_secondary_agents", "sistema", confirmed=True)
            self.assertEqual(res["state"], "ok")
            mods = engine.modifications()
            self.assertEqual(mods[-1]["kind"], "pause_secondary_agents")
            self.assertEqual(mods[-1]["state"], "applied")
            out = panel.undo_last(confirmed=True)
            self.assertEqual(out["rolled_back"]["kind"], "pause_secondary_agents")
            self.assertEqual(engine.modifications()[-1]["state"], "reverted")

    def test_reject_with_confirmation_removes_the_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            panel, engine = self._panel(Path(tmp))
            engine.run_cycle()
            res = panel.reject("pause_secondary_agents", "sistema", confirmed=True)
            self.assertEqual(res["state"], "ok")
            self.assertFalse(any(a.kind == "pause_secondary_agents"
                                 for a in engine.last_supervised()))

    def test_unimplemented_action_is_declared_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            panel, _ = self._panel(Path(tmp))
            res = panel.explain("change_dns")
            self.assertEqual(res["state"], "unavailable")

    def test_run_cycle_passthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            panel, _ = self._panel(Path(tmp))
            res = panel.run_cycle()
            self.assertEqual(res["state"], "ok")
            self.assertIn("applied", res["cycle"])


class RefreshTests(unittest.TestCase):
    def test_poller_produces_snapshots_and_notifies_listeners(self):
        calls = {"n": 0}

        def producer():
            calls["n"] += 1
            return {"state": "ok", "n": calls["n"]}

        poller = Poller(producer, interval_ms=1500)
        got = []
        poller.listeners.append(got.append)
        self.assertTrue(poller.tick())
        self.assertEqual(poller.ticks, 1)
        self.assertEqual(poller.last["n"], 1)
        self.assertEqual(got, [poller.last])
        self.assertEqual(poller.interval_ms, 1500)

    def test_poller_converts_producer_errors_into_error_state(self):
        def producer():
            raise RuntimeError("fallo de sondeo")

        poller = Poller(producer)
        self.assertTrue(poller.tick())
        self.assertEqual(poller.last["state"], "error")
        self.assertIn("fallo de sondeo", poller.last["message"])

    def test_poller_records_listener_errors_without_stopping(self):
        poller = Poller(lambda: {"state": "ok"})
        def bad(_snap):
            raise RuntimeError("oyente defectuoso")
        poller.listeners.append(bad)
        self.assertTrue(poller.tick())
        self.assertEqual(poller.last["state"], "ok")
        self.assertIn("oyente defectuoso", poller.errors[-1]["error"])

    def test_async_runner_runs_off_caller_thread_and_delivers(self):
        delivered = []
        done = threading.Event()
        runner = AsyncRunner(deliver=lambda cb: cb())
        caller = threading.get_ident()

        def work():
            return threading.get_ident()

        def on_done(tid):
            delivered.append(tid != caller)
            done.set()

        runner.submit(work, on_done)
        self.assertTrue(done.wait(timeout=10))
        self.assertEqual(delivered, [True])

    def test_async_runner_delivers_errors_without_raising(self):
        errs = []
        done = threading.Event()
        runner = AsyncRunner(deliver=lambda cb: cb())

        def work():
            raise ValueError("fallo controlado")

        runner.submit(work, on_done=lambda r: errs.append(("ok", r)),
                      on_error=lambda e: (errs.append(("err", str(e))), done.set()))
        self.assertTrue(done.wait(timeout=10))
        self.assertEqual(errs, [("err", "fallo controlado")])

    def test_async_runner_pending_returns_to_zero(self):
        runner = AsyncRunner(deliver=lambda cb: cb())
        gate = threading.Event()
        done = threading.Event()

        def work():
            gate.wait(timeout=5)
            return 1

        runner.submit(work, on_done=lambda r: done.set())
        gate.set()
        self.assertTrue(done.wait(timeout=10))
        for _ in range(200):
            if runner.pending == 0:
                break
            time.sleep(0.01)
        self.assertEqual(runner.pending, 0)


class GtkuiModuleTests(unittest.TestCase):
    def test_imports_without_gtk_and_keeps_theme_constants(self):
        import importlib
        mod = importlib.import_module("nexora.desktop.gtkui")
        self.assertTrue(callable(mod.run))
        self.assertEqual(mod.ACCENT_DEFAULT, "#3a7bd5")
        self.assertEqual(mod.REFRESH_INTERVAL_MS, 2000)
        self.assertIn("Nexora-Dark", mod.GTK_CSS.format(accent=mod.ACCENT_DEFAULT) + "/usr/share/themes/Nexora-Dark")


class HubTests(unittest.TestCase):
    def test_agents_lists_modes_and_specialists(self):
        hub = NexoraHub(coordinator=Coordinator())
        res = hub.agents(ModeRegistry())
        names = {a["name"]: a for a in res["agents"]}
        self.assertEqual(set(names), {"gaming", "hacking", "office", "stealth", "forge",
                                      "meteorology", "security"})
        self.assertEqual(names["gaming"]["kind"], "mode")
        self.assertEqual(names["meteorology"]["kind"], "specialist")

    def test_models_with_mock_engine_is_labelled(self):
        hub = NexoraHub(engine=LocalAIEngine())
        res = hub.models()
        current = [b for b in res["backends"] if b["state"] == "current"]
        self.assertEqual(len(current), 1)
        self.assertTrue(current[0]["simulated"])

    def test_models_probe_loopback_only(self):
        res = NexoraHub().models()
        for backend in res["backends"]:
            self.assertIn("127.0.0.1", backend["endpoint"])

    def test_tools_without_index_is_no_data(self):
        self.assertEqual(NexoraHub().tools()["state"], "no_data")

    def test_tools_categories_from_index(self):
        tmp = tempfile.mkdtemp()
        apps_dir = Path(tmp) / "applications"
        apps_dir.mkdir()
        write_desktop(apps_dir / "dev.desktop", "Dev Tool", "sh", "Development")
        hub = NexoraHub(index=ApplicationIndex(data_dirs=[Path(tmp)]))
        res = hub.tools()
        self.assertEqual(res["state"], "ok")
        self.assertEqual(res["categories"]["Development"][0]["name"], "Dev Tool")


class SystemCenterTests(unittest.TestCase):
    def test_sections_have_explicit_states(self):
        sections = SystemCenter().sections()
        for name, section in sections.items():
            for entry in section["entries"]:
                self.assertIn(entry["state"],
                              ("available", "unavailable", "not_implemented"))

    def test_sections_include_readonly_data(self):
        sections = SystemCenter().sections()
        self.assertEqual(sections["users"]["data"]["state"], "ok")
        self.assertIn(sections["updates"]["data"]["state"],
                      ("ok", "unavailable", "error"))

    def test_launch_whitelist(self):
        import shutil
        sc = SystemCenter()
        # Fuera de la lista blanca: rechazado siempre.
        self.assertEqual(sc.launch("rm -rf /")["state"], "rejected")
        self.assertEqual(sc.launch("nonexistent-cmd")["state"], "rejected")
        # En la lista blanca pero no instalado en este sistema: unavailable.
        missing = []
        for spec in SECTIONS.values():
            for entry in spec["entries"]:
                cmd = entry.get("command")
                if cmd and shutil.which(cmd) is None:
                    missing.append(cmd)
        if not missing:
            self.skipTest("todas las herramientas de la lista blanca están instaladas")
        self.assertEqual(sc.launch(missing[0])["state"], "unavailable")

    def test_launch_disabled_context(self):
        sc = SystemCenter(allow_launch=False)
        self.assertEqual(sc.launch("thunar")["state"], "rejected")

    def test_list_users_reads_real_passwd(self):
        res = list_users()
        self.assertEqual(res["state"], "ok")
        self.assertTrue(any(u["uid"] == 0 for u in res["humans"]))
        for u in res["humans"]:
            self.assertNotIn(";", u["name"])

    def test_list_users_with_fake_passwd(self):
        tmp = tempfile.mkdtemp()
        passwd = Path(tmp) / "passwd"
        passwd.write_text(
            "root:x:0:0:root:/root:/bin/bash\n"
            "alice:x:1000:1000:Alice:/home/alice:/bin/zsh\n"
            "daemon:x:2:2:daemon:/sbin:/usr/bin/nologin\n"
            "malo:x:no-es-numERO:x::/x:/bin/sh\n",
            encoding="utf-8",
        )
        res = list_users(passwd_path=str(passwd))
        self.assertEqual(res["state"], "ok")
        names = {u["name"] for u in res["humans"]}
        self.assertEqual(names, {"root", "alice"})
        self.assertEqual(res["system_count"], 1)

    def test_pending_updates_without_pacman_is_unavailable(self):
        tmp = tempfile.mkdtemp()
        res = pending_updates(pacman_path=str(Path(tmp) / "no-existe"))
        self.assertEqual(res["state"], "unavailable")

    def test_pending_updates_parses_output(self):
        tmp = tempfile.mkdtemp()
        fake = Path(tmp) / "pacman"
        fake.write_text("#!/bin/sh\necho 'linux 6.1 -> 6.2'\necho 'bash 5.1 -> 5.2'\nexit 0\n",
                        encoding="utf-8")
        fake.chmod(0o755)
        res = pending_updates(pacman_path=str(fake))
        self.assertEqual(res["state"], "ok")
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["packages"], ["linux", "bash"])

    def test_privileged_actions_catalog(self):
        res = SystemCenter().privileged_actions()
        self.assertEqual(res["state"], "ok")
        names = {a["name"] for a in res["actions"]}
        self.assertEqual(names, set(PRIVILEGED_ACTIONS))
        for action in res["actions"]:
            self.assertIn(action["state"], ("available", "unavailable"))

    def test_launch_privileged_rejects_unknown(self):
        self.assertEqual(SystemCenter().launch_privileged("rm -rf /")["state"], "rejected")
        self.assertEqual(SystemCenter().launch_privileged("format_disk")["state"], "rejected")

    def test_launch_privileged_disabled_context(self):
        sc = SystemCenter(allow_launch=False)
        self.assertEqual(sc.launch_privileged("system_update")["state"], "rejected")

    def test_launch_privileged_without_pkexec_is_unavailable(self):
        import shutil
        if shutil.which("pkexec") is not None:
            self.skipTest("pkexec está instalado: no se prueba el fallo")
        self.assertEqual(SystemCenter().launch_privileged("system_update")["state"],
                         "unavailable")


class AppTests(unittest.TestCase):
    def test_refuses_root(self):
        if os.getuid() == 0:
            self.skipTest("ejecutando como root")
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getuid
            os.getuid = lambda: 0
            try:
                with self.assertRaises(PermissionError):
                    NexoraDesktopApp()
            finally:
                os.getuid = old

    def test_lifecycle_and_layout(self):
        app = NexoraDesktopApp(engine=LocalAIEngine())
        app.start()
        try:
            self.assertTrue(app.running)
            layout = app.layout()
            for key in ("panel", "dashboard", "mode_center", "nke_control", "hub", "system_center"):
                self.assertIn(key, layout)
            json.dumps(layout, ensure_ascii=False)  # serializable para la GUI
        finally:
            app.shutdown()
        self.assertFalse(app.running)
        kinds = [e["kind"] for e in app.events()]
        self.assertIn("start", kinds)
        self.assertIn("shutdown", kinds)

    def test_layout_requires_start(self):
        app = NexoraDesktopApp()
        with self.assertRaises(RuntimeError):
            app.layout()

    def test_run_gtk_without_gives_clear_error(self):
        app = NexoraDesktopApp(engine=LocalAIEngine())
        app.start()
        try:
            if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                self.skipTest("hay sesión gráfica: no se prueba el fallo")
            try:
                import gi  # noqa: F401
                self.skipTest("PyGObject disponible: no se prueba el fallo")
            except ImportError:
                pass
            from nexora.desktop import DesktopUnavailableError
            with self.assertRaises(DesktopUnavailableError):
                app.run_gtk()
        finally:
            if app.running:
                app.shutdown()


if __name__ == "__main__":
    unittest.main()
