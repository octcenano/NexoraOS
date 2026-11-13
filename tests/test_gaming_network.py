"""Tests del Gaming Network Engine (NGNE): sin red real ni servidores externos."""

import os
import subprocess
import tempfile
import unittest

from nexora.gaming.network import optimizer as gn_optimizer
from nexora.gaming.network import profiles as gn_profiles
from nexora.gaming.network.diagnostics import NetworkDiagnostics


PING_OK = """PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.
64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=1.05 ms
64 bytes from 192.168.1.1: icmp_seq=2 ttl=64 time=1.35 ms

--- 192.168.1.1 ping statistics ---
10 packets transmitted, 10 received, 0% packet loss, time 908ms
rtt min/avg/max/mdev = 0.900/1.200/2.000/0.300 ms
"""

PING_LOSS = """PING 9.9.9.9 (9.9.9.9) 56(84) bytes of data.
64 bytes from 9.9.9.9: icmp_seq=1 ttl=57 time=12.0 ms

--- 9.9.9.9 ping statistics ---
10 packets transmitted, 8 received, 20% packet loss, time 908ms
rtt min/avg/max/mdev = 11.0/12.5/14.0/0.900 ms
"""

PING_DEAD = """PING 10.255.255.1 (10.255.255.1) 56(84) bytes of data.

--- 10.255.255.1 ping statistics ---
10 packets transmitted, 0 received, 100% packet loss, time 908ms
"""

IW_5GHZ = """Connected to aa:bb:cc:dd:ee:ff (on wlan0)
	SSID: NexoraNet
	freq: 5180
	signal: -52 dBm
"""

SHOW_NOQUEUE = "qdisc noqueue 0: root refcnt 2\n"
SHOW_FQ_CODEL = ("qdisc fq_codel 8001: root refcnt 2 limit 10240p flows 1024 "
                 "quantum 1514 target 5.0ms interval 100.0ms\n")
SHOW_CAKE = ("qdisc cake 8001: root bandwidth unlimited diffserv4 triple-isolate "
             "nonat nowash no-ack-filter split-gso rtt 100ms noatm\n")
SHOW_PFIFO = "qdisc pfifo_fast 0: root refcnt 2 bands 3 priomap 1 2 2 2 1 2 0 0 1 1 1 1 1 1 1 1\n"
SHOW_HTB = "qdisc htb 8001: root refcnt 2 r2q 10 default 0 direct_packets_stat 0\n"


class FakeRunner:
    """Ejecutor falso: registra llamadas y devuelve salidas fijas. Sin red."""

    def __init__(self, outputs=None, error=None):
        self.calls = []
        self.outputs = outputs or {}
        self.error = error

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if self.error is not None:
            raise self.error
        key = argv[0]
        if key not in self.outputs:
            raise AssertionError("comando inesperado: " + key)
        rc, out, err = self.outputs[key]
        return subprocess.CompletedProcess(argv, rc, stdout=out, stderr=err)


class QueueFakeRunner:
    """Ejecutor falso con guion secuencial: cada llamada consume la siguiente
    salida cuyo filtro coincide con el argv. Para encadenar tc show/replace."""

    def __init__(self):
        self.calls = []
        self.script = []

    def queue(self, contains, rc=0, out="", err=""):
        self.script.append([contains, rc, out, err])

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        for i, item in enumerate(self.script):
            if item[0] in joined:
                self.script.pop(i)
                return subprocess.CompletedProcess(argv, item[1], stdout=item[2],
                                                   stderr=item[3])
        raise AssertionError("comando sin guion: " + joined)


def make_env(tmp):
    """Árbol falso de /sys/class/net, /proc y resolv.conf. Devuelve rutas."""
    sys_net = os.path.join(tmp, "sys", "class", "net")

    def wf(*parts, content=None):
        path = os.path.join(sys_net, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content if content is not None else "")
        return path

    wf("lo", "operstate", content="unknown\n")
    wf("lo", "mtu", content="65536\n")
    wf("eth0", "operstate", content="up\n")
    wf("eth0", "mtu", content="1500\n")
    wf("eth0", "carrier", content="1\n")
    wf("eth0", "speed", content="1000\n")
    wf("eth0", "duplex", content="full\n")
    for stat, value in (("rx_errors", "0"), ("tx_errors", "2"),
                        ("rx_dropped", "0"), ("tx_dropped", "0")):
        wf("eth0", "statistics", stat, content=value + "\n")
    wf("eth1", "operstate", content="down\n")
    wf("eth1", "mtu", content="1500\n")
    wf("eth1", "carrier", content="0\n")
    for stat in ("rx_errors", "tx_errors", "rx_dropped", "tx_dropped"):
        wf("eth1", "statistics", stat, content="0\n")
    wf("wlan0", "operstate", content="up\n")
    wf("wlan0", "mtu", content="1500\n")
    os.makedirs(os.path.join(sys_net, "wlan0", "wireless"))
    for stat in ("rx_errors", "tx_errors", "rx_dropped", "tx_dropped"):
        wf("wlan0", "statistics", stat, content="0\n")

    route = os.path.join(tmp, "proc", "net", "route")
    os.makedirs(os.path.dirname(route), exist_ok=True)
    with open(route, "w", encoding="utf-8") as fh:
        fh.write("Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n")
        fh.write("eth0\t00000000\tC0A80101\t0003\t0\t0\t100\t00000000\t0\t0\t0\n")
        fh.write("wlan0\t00000000\t00000000\t0001\t0\t0\t600\t00000000\t0\t0\t0\n")

    wireless = os.path.join(tmp, "proc", "net", "wireless")
    with open(wireless, "w", encoding="utf-8") as fh:
        fh.write("Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n")
        fh.write(" face | tus | link level noise|  nwid  crypt   frag  retry   misc | beacon | 22\n")
        fh.write(" wlan0: 0000   70.  -52.  -256        0      0      0      0      0        0\n")

    resolv = os.path.join(tmp, "etc", "resolv.conf")
    os.makedirs(os.path.dirname(resolv), exist_ok=True)
    with open(resolv, "w", encoding="utf-8") as fh:
        fh.write("# Generated by NetworkManager\n")
        fh.write("nameserver 1.1.1.1\n")
        fh.write("search lan\n")
        fh.write("nameserver 8.8.8.8\n")

    ping = os.path.join(tmp, "ping")
    with open(ping, "w", encoding="utf-8") as fh:
        fh.write("# ping simulado para pruebas\n")

    return {
        "sys_net": sys_net, "route": route, "wireless": wireless,
        "resolv": resolv, "ping": ping,
    }


def make_diag(env, runner=None, iw_path=None, **kw):
    return NetworkDiagnostics(
        sys_net=env["sys_net"], route_path=env["route"],
        wireless_path=env["wireless"], resolv_path=env["resolv"],
        runner=runner, ping_path=env["ping"], iw_path=iw_path, **kw
    )


def make_tools(tmp):
    """Crea binarios ficticios tc y pkexec y devuelve sus rutas."""
    tc = os.path.join(tmp, "tc")
    pk = os.path.join(tmp, "pkexec")
    rc = os.path.join(tmp, "resolvectl")
    for path in (tc, pk, rc):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# binario simulado para pruebas\n")
    return tc, pk, rc


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.env = make_env(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_interfaces_lee_datos_reales_del_arbol(self):
        d = make_diag(self.env)
        r = d.interfaces()
        self.assertEqual(r["state"], "ok")
        by_name = {i["name"]: i for i in r["interfaces"]}
        self.assertEqual(by_name["eth0"]["type"], "ethernet")
        self.assertEqual(by_name["eth0"]["operstate"], "up")
        self.assertEqual(by_name["eth0"]["mtu"], 1500)
        self.assertEqual(by_name["eth0"]["speed_mbps"], 1000)
        self.assertEqual(by_name["eth0"]["duplex"], "full")
        self.assertEqual(by_name["eth0"]["statistics"]["tx_errors"], 2)
        self.assertEqual(by_name["wlan0"]["type"], "wireless")
        self.assertEqual(by_name["wlan0"]["signal_dbm"], -52.0)

    def test_interfaz_caida_marca_velocidad_no_disponible(self):
        d = make_diag(self.env)
        r = d.interfaces()
        by_name = {i["name"]: i for i in r["interfaces"]}
        eth1 = by_name["eth1"]
        self.assertIsNone(eth1["speed_mbps"])
        self.assertIn("no disponible", eth1["speed_note"])

    def test_wifi_banda_con_iw(self):
        runner = FakeRunner(outputs={self.env["ping"]: (0, PING_OK, "")})
        iw = os.path.join(self._tmp.name, "iw")
        with open(iw, "w", encoding="utf-8") as fh:
            fh.write("# iw simulado\n")
        runner.outputs[iw] = (0, IW_5GHZ, "")
        d = make_diag(self.env, runner=runner, iw_path=iw)
        r = d.interfaces()
        wlan = {i["name"]: i for i in r["interfaces"]}["wlan0"]
        self.assertTrue(wlan["band"]["available"])
        self.assertEqual(wlan["band"]["band"], "5 GHz")
        self.assertEqual(wlan["band"]["signal_dbm_iw"], -52.0)

    def test_wifi_banda_no_disponible_sin_iw(self):
        d = make_diag(self.env)
        r = d.interfaces()
        wlan = {i["name"]: i for i in r["interfaces"]}["wlan0"]
        self.assertFalse(wlan["band"]["available"])
        self.assertIn("iw", wlan["band"]["note"])

    def test_gateway_desde_proc_route(self):
        d = make_diag(self.env)
        gw = d.gateway()
        self.assertEqual(gw["state"], "ok")
        self.assertEqual(gw["ip"], "192.168.1.1")
        self.assertEqual(gw["iface"], "eth0")

    def test_gateway_sin_ruta_por_defecto(self):
        route = self.env["route"]
        with open(route, "w", encoding="utf-8") as fh:
            fh.write("Iface\tDestination\tGateway\tFlags\n")
            fh.write("eth0\t00000000\t00000000\t0001\n")
        d = make_diag(self.env)
        gw = d.gateway()
        self.assertEqual(gw["state"], "unavailable")
        self.assertIn("sin ruta", gw["note"])

    def test_dns_desde_resolv_conf(self):
        d = make_diag(self.env)
        dns = d.dns_servers()
        self.assertEqual(dns["state"], "ok")
        self.assertEqual(dns["servers"], ["1.1.1.1", "8.8.8.8"])

    def test_dns_sin_servidores(self):
        with open(self.env["resolv"], "w", encoding="utf-8") as fh:
            fh.write("# solo comentarios\nsearch lan\n")
        d = make_diag(self.env)
        dns = d.dns_servers()
        self.assertEqual(dns["state"], "unavailable")
        self.assertEqual(dns["servers"], [])

    def test_ping_analiza_perdida_media_y_jitter(self):
        runner = FakeRunner(outputs={self.env["ping"]: (0, PING_OK, "")})
        d = make_diag(self.env, runner=runner)
        r = d.ping("192.168.1.1")
        self.assertEqual(r["state"], "ok")
        self.assertEqual(r["loss_pct"], 0.0)
        self.assertEqual(r["avg_ms"], 1.2)
        self.assertEqual(r["jitter_ms"], 0.3)
        self.assertEqual(runner.calls[0][-1], "192.168.1.1")
        self.assertIn("-c", runner.calls[0])

    def test_ping_con_perdida_parcial_es_degraded(self):
        runner = FakeRunner(outputs={self.env["ping"]: (0, PING_LOSS, "")})
        d = make_diag(self.env, runner=runner)
        r = d.ping("9.9.9.9")
        self.assertEqual(r["state"], "degraded")
        self.assertEqual(r["loss_pct"], 20.0)

    def test_ping_sin_respuestas_es_error(self):
        runner = FakeRunner(outputs={self.env["ping"]: (1, PING_DEAD, "")})
        d = make_diag(self.env, runner=runner)
        r = d.ping("10.255.255.1")
        self.assertEqual(r["state"], "error")
        self.assertEqual(r["loss_pct"], 100.0)
        self.assertIsNone(r["avg_ms"])

    def test_ping_sin_binario_es_no_disponible(self):
        d = make_diag(self.env, ping_path="/no/existe/ping")
        r = d.ping("192.168.1.1")
        self.assertEqual(r["state"], "unavailable")
        self.assertIn("ping", r["note"])

    def test_ping_timeout_es_error(self):
        runner = FakeRunner(error=subprocess.TimeoutExpired(cmd="ping", timeout=15))
        d = make_diag(self.env, runner=runner)
        r = d.ping("192.168.1.1")
        self.assertEqual(r["state"], "error")
        self.assertIn("tiempo de espera", r["note"])

    def test_ping_error_de_ejecucion_es_error(self):
        runner = FakeRunner(error=OSError("permiso denegado"))
        d = make_diag(self.env, runner=runner)
        r = d.ping("192.168.1.1")
        self.assertEqual(r["state"], "error")
        self.assertIn("OSError", r["note"])

    def test_latency_report_solo_local_por_defecto(self):
        runner = FakeRunner(outputs={self.env["ping"]: (0, PING_OK, "")})
        d = make_diag(self.env, runner=runner)
        r = d.latency_report()
        self.assertEqual(r["local"]["state"], "ok")
        self.assertEqual(r["local"]["target"], "192.168.1.1")
        self.assertEqual(r["internet"]["state"], "unavailable")
        self.assertIn("explícitamente", r["internet"]["note"])
        self.assertEqual(r["game_server"]["state"], "unavailable")
        # solo se contactó con la puerta de enlace: nunca con servidores externos
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("192.168.1.1", runner.calls[0])

    def test_latency_report_con_objetivos_explícitos(self):
        runner = FakeRunner(outputs={
            self.env["ping"]: (0, PING_OK, ""),
        })
        d = make_diag(self.env, runner=runner)
        r = d.latency_report(internet_target="9.9.9.9", game_server="1.2.3.4")
        self.assertEqual(r["internet"]["target"], "9.9.9.9")
        self.assertEqual(r["game_server"]["target"], "1.2.3.4")
        self.assertEqual(len(runner.calls), 3)

    def test_summary_declara_bufferbloat_no_disponible(self):
        runner = FakeRunner(outputs={self.env["ping"]: (0, PING_OK, "")})
        d = make_diag(self.env, runner=runner)
        s = d.summary()
        self.assertEqual(s["scope"], "readonly_diagnostics")
        self.assertEqual(s["bufferbloat"]["state"], "unavailable")
        self.assertIn("no se simula", s["bufferbloat"]["note"])

    def test_parametros_invalidos_lanzan_valueerror(self):
        with self.assertRaises(ValueError):
            NetworkDiagnostics(ping_count=0)
        with self.assertRaises(ValueError):
            NetworkDiagnostics(ping_interval_s=0)
        with self.assertRaises(ValueError):
            NetworkDiagnostics(ping_timeout_s=-1)

    def test_ping_sin_objetivo_es_no_disponible(self):
        d = make_diag(self.env)
        r = d.ping("")
        self.assertEqual(r["state"], "unavailable")


class ProfilesTests(unittest.TestCase):
    def test_catalogo_de_seis_perfiles(self):
        self.assertEqual(len(gn_profiles.GAMING_PROFILES), 6)
        self.assertEqual(tuple(gn_profiles.GAMING_PROFILES), gn_profiles.PROFILE_ORDER)

    def test_hardware_compacto_sustituye_cake_por_fq_codel(self):
        r = gn_profiles.adapt_profile("low_latency", {"hardware_tier": "compact"})
        self.assertEqual(r["effective"]["qdisc"], "fq_codel")
        self.assertTrue(any("fq-codel" in a for a in r["adaptations"]))

    def test_sin_alternativa_de_cola_deja_qdisc_none(self):
        r = gn_profiles.adapt_profile("balanced", {"qdiscs_available": ["htb"]})
        self.assertIsNone(r["effective"]["qdisc"])
        self.assertTrue(any("no se toca nada" in a for a in r["adaptations"]))

    def test_alternativa_de_cola_disponible_se_usa(self):
        r = gn_profiles.adapt_profile("balanced", {"qdiscs_available": ["cake"]})
        self.assertEqual(r["effective"]["qdisc"], "cake")
        self.assertTrue(any("se usa cake" in a for a in r["adaptations"]))

    def test_custom_valida_parametros(self):
        r = gn_profiles.adapt_profile("custom", {"custom_params": {
            "qdisc": "cake", "qdisc_params": {"bandwidth": "20mbit"},
        }})
        self.assertEqual(r["effective"]["qdisc"], "cake")
        self.assertEqual(r["effective"]["qdisc_params"]["bandwidth"], "20mbit")
        with self.assertRaises(ValueError):
            gn_profiles.adapt_profile("custom", {"custom_params": {"inventado": 1}})
        with self.assertRaises(ValueError):
            gn_profiles.adapt_profile("custom", {"custom_params": {"qdisc": "htb"}})

    def test_perfil_desconocido_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            gn_profiles.adapt_profile("turbo")

    def test_wifi_con_perfil_ethernet_avisa(self):
        r = gn_profiles.adapt_profile("ethernet", {"link_type": "wifi"})
        self.assertTrue(any("Wi-Fi" in a for a in r["adaptations"]))


class OptimizerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.env = make_env(self._tmp.name)
        self.tc, self.pk, self.rc = make_tools(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _opt(self, runner):
        return gn_optimizer.QueueOptimizer(
            runner=runner, tc_path=self.tc, pkexec_path=self.pk,
            sys_net=self.env["sys_net"],
        )

    def test_current_qdisc_interpreta_salida_real(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", out=SHOW_FQ_CODEL)
        opt = self._opt(runner)
        r = opt.current_qdisc("eth0")
        self.assertEqual(r["state"], "ok")
        self.assertEqual(r["kind"], "fq_codel")

    def test_current_qdisc_sin_tc_es_no_disponible(self):
        opt = gn_optimizer.QueueOptimizer(runner=QueueFakeRunner(),
                                          tc_path="/no/existe/tc",
                                          sys_net=self.env["sys_net"])
        r = opt.current_qdisc("eth0")
        self.assertEqual(r["state"], "unavailable")

    def test_compatibility_sin_pkexec_es_no_disponible(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", out=SHOW_NOQUEUE)
        opt = gn_optimizer.QueueOptimizer(runner=runner, tc_path=self.tc,
                                          pkexec_path="/no/existe/pkexec",
                                          sys_net=self.env["sys_net"])
        r = opt.compatibility("eth0")
        self.assertEqual(r["state"], "unavailable")
        self.assertFalse(r["pkexec"])

    def test_apply_sin_confirmacion_no_ejecuta_nada(self):
        runner = QueueFakeRunner()
        opt = self._opt(runner)
        r = opt.apply_qdisc("eth0", "fq_codel")
        self.assertEqual(r["state"], "confirmation_required")
        self.assertEqual(runner.calls, [])

    def test_apply_rechaza_cola_y_parametros_desconocidos(self):
        opt = self._opt(QueueFakeRunner())
        r = opt.apply_qdisc("eth0", "htb", user_approved=True)
        self.assertEqual(r["state"], "rejected")
        r2 = opt.apply_qdisc("eth0", "cake", params={"inventado": 1}, user_approved=True)
        self.assertEqual(r2["state"], "rejected")
        r3 = opt.apply_qdisc("noexiste", "fq_codel", user_approved=True)
        self.assertEqual(r3["state"], "rejected")

    def test_apply_captura_previo_aplica_y_verifica(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", out=SHOW_NOQUEUE)
        runner.queue("qdisc replace", rc=0)
        runner.queue("qdisc show", out=SHOW_FQ_CODEL)
        opt = self._opt(runner)
        r = opt.apply_qdisc("eth0", "fq_codel", user_approved=True)
        self.assertEqual(r["state"], "ok")
        self.assertTrue(r["verified"])
        mod = r["modification"]
        self.assertEqual(mod["previous_kind"], "noqueue")
        self.assertEqual(mod["state"], "applied")
        self.assertEqual(runner.calls[0], [self.pk, self.tc, "qdisc", "replace",
                                           "dev", "eth0", "root", "fq_codel"])

    def test_apply_sin_lectura_previa_no_toca_nada(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", rc=1, err="Cannot find device")
        opt = self._opt(runner)
        r = opt.apply_qdisc("eth0", "fq_codel", user_approved=True)
        self.assertEqual(r["state"], "error")
        self.assertIn("no se toca nada", r["note"])
        self.assertEqual(len(runner.calls), 1)  # solo la lectura, ningún cambio

    def test_apply_con_cola_previa_no_restaurable_rechaza(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", out=SHOW_HTB)
        opt = self._opt(runner)
        r = opt.apply_qdisc("eth0", "fq_codel", user_approved=True)
        self.assertEqual(r["state"], "rejected")
        self.assertIn("htb", r["note"])
        self.assertEqual(len(runner.calls), 1)

    def test_verificacion_fallida_restaura_estado_previo(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", out=SHOW_NOQUEUE)
        runner.queue("qdisc replace", rc=0)
        runner.queue("qdisc show", out=SHOW_NOQUEUE)  # la cola no cambió de verdad
        runner.queue("qdisc del", rc=0)               # restauración
        runner.queue("qdisc show", out=SHOW_NOQUEUE)  # verificación de la restauración
        opt = self._opt(runner)
        r = opt.apply_qdisc("eth0", "fq_codel", user_approved=True)
        self.assertEqual(r["state"], "error")
        self.assertEqual(r["restore"]["state"], "ok")
        self.assertEqual(opt.modifications(), [])

    def test_undo_last_restaura_pfifo_fast(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", out=SHOW_PFIFO)
        runner.queue("qdisc replace", rc=0)
        runner.queue("qdisc show", out=SHOW_FQ_CODEL)
        opt = self._opt(runner)
        r = opt.apply_qdisc("eth0", "fq_codel", user_approved=True)
        self.assertEqual(r["state"], "ok")
        runner.queue("qdisc replace", rc=0)
        runner.queue("qdisc show", out=SHOW_PFIFO)
        u = opt.undo_last()
        self.assertEqual(u["state"], "ok")
        self.assertEqual(u["modification"]["previous_kind"], "pfifo_fast")
        self.assertEqual(u["modification"]["state"], "reverted")

    def test_cake_con_bandwidth_y_diffserv_en_argv(self):
        runner = QueueFakeRunner()
        runner.queue("qdisc show", out=SHOW_NOQUEUE)
        runner.queue("qdisc replace", rc=0)
        runner.queue("qdisc show", out=SHOW_CAKE)
        opt = self._opt(runner)
        r = opt.apply_qdisc("eth0", "cake",
                            params={"bandwidth": "50mbit", "diffserv": "diffserv4"},
                            user_approved=True)
        self.assertEqual(r["state"], "ok")
        self.assertEqual(runner.calls[0][-4:], ["cake", "bandwidth", "50mbit", "diffserv4"])

    def test_undo_sin_modificaciones_es_no_disponible(self):
        opt = self._opt(QueueFakeRunner())
        r = opt.undo_last()
        self.assertEqual(r["state"], "unavailable")


class DnsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.env = make_env(self._tmp.name)
        self.tc, self.pk, self.rc = make_tools(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _dns(self, runner):
        return gn_optimizer.DnsOptimizer(
            runner=runner, resolvectl_path=self.rc, pkexec_path=self.pk,
            resolv_path=self.env["resolv"],
        )

    def test_sin_consentimiento_no_ejecuta_nada(self):
        runner = QueueFakeRunner()
        dns = self._dns(runner)
        r = dns.set_servers("eth0", ["9.9.9.9"])
        self.assertEqual(r["state"], "confirmation_required")
        self.assertEqual(runner.calls, [])

    def test_servidor_invalido_rechazado(self):
        dns = self._dns(QueueFakeRunner())
        r = dns.set_servers("eth0", ["no-es-una-ip"], user_approved=True)
        self.assertEqual(r["state"], "rejected")
        self.assertIn("no es una IP", r["note"])

    def test_aplica_y_verifica_con_resolvectl(self):
        runner = QueueFakeRunner()
        runner.queue("dns eth0", rc=0)                      # aplicar
        runner.queue("dns eth0", out="Link 2 (eth0): 9.9.9.9 149.112.112.112\n")
        dns = self._dns(runner)
        r = dns.set_servers("eth0", ["9.9.9.9", "149.112.112.112"], user_approved=True)
        self.assertEqual(r["state"], "ok")
        self.assertTrue(r["verified"])
        mod = r["modification"]
        self.assertEqual(mod["previous_servers"], ["1.1.1.1", "8.8.8.8"])
        self.assertEqual(runner.calls[0], [self.pk, self.rc, "dns", "eth0",
                                           "9.9.9.9", "149.112.112.112"])

    def test_undo_restaura_los_servidores_previos(self):
        runner = QueueFakeRunner()
        runner.queue("dns eth0", rc=0)
        runner.queue("dns eth0", out="Link 2 (eth0): 9.9.9.9\n")
        dns = self._dns(runner)
        r = dns.set_servers("eth0", ["9.9.9.9"], user_approved=True)
        self.assertEqual(r["state"], "ok")
        runner.queue("dns eth0", rc=0)                      # restaurar
        runner.queue("dns eth0", out="Link 2 (eth0): 1.1.1.1 8.8.8.8\n")
        u = dns.undo_last()
        self.assertEqual(u["state"], "ok")
        self.assertEqual(runner.calls[-2], [self.pk, self.rc, "dns", "eth0",
                                            "1.1.1.1", "8.8.8.8"])

    def test_sin_resolvectl_es_no_disponible(self):
        dns = gn_optimizer.DnsOptimizer(runner=QueueFakeRunner(),
                                        resolvectl_path="/no/existe/resolvectl",
                                        pkexec_path=self.pk,
                                        resolv_path=self.env["resolv"])
        r = dns.set_servers("eth0", ["9.9.9.9"], user_approved=True)
        self.assertEqual(r["state"], "unavailable")

    def test_verificacion_fallida_restaura(self):
        runner = QueueFakeRunner()
        runner.queue("dns eth0", rc=0)                      # aplicar
        runner.queue("dns eth0", out="Link 2 (eth0):\n")    # verificación: vacío
        runner.queue("revert", rc=0)                        # restauración
        dns = self._dns(runner)
        r = dns.set_servers("eth0", ["9.9.9.9"], user_approved=True)
        self.assertEqual(r["state"], "error")
        self.assertEqual(r["restore"]["state"], "ok")
        self.assertEqual(dns.modifications(), [])


if __name__ == "__main__":
    unittest.main()
