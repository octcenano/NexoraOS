"""Tests del agente Security: auditoría de solo lectura, recomendaciones e informe."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import nexora.agents.security as security
from nexora.agents.security import (
    SecurityAgent,
    run_defensive_audit,
    write_report,
)


class ReadOnlyAuditTest(unittest.TestCase):
    def test_auditoria_basica_sin_privilegios(self):
        report = run_defensive_audit({"vault": {"backend": "memory"}, "version": "0.4.0-beta"})
        self.assertEqual(report["scope"], "read_only_defensive")
        self.assertIn(report["overall"], ("ok", "warn", "fail"))
        names = {c["name"] for c in report["checks"]}
        self.assertTrue({"config", "vault", "listening_sockets", "updates",
                         "world_writable_files"} <= names)

    def test_recomendaciones_para_warn(self):
        with mock.patch.object(security, "_config_file_permissions", return_value="0o644"):
            report = run_defensive_audit({"vault": {"backend": "memory"}})
        self.assertTrue(any("600" in r for r in report["recommendations"]))

    def test_config_con_secreto_es_fail(self):
        report = run_defensive_audit({"api_key": "sk-supersecreto-1234567890"})
        check = next(c for c in report["checks"] if c["name"] == "config_secrets")
        self.assertEqual(check["status"], "fail")
        self.assertEqual(report["overall"], "fail")

    def test_inventario_de_sockets(self):
        sockets = security._listening_sockets()
        if sockets is None:
            self.skipTest("/proc/net/tcp no disponible en este entorno")
        self.assertIsInstance(sockets, list)
        for family, port in sockets:
            self.assertIn(family, ("tcp", "tcp6"))
            self.assertTrue(0 <= port <= 65535)

    def test_inventario_lee_puerto_en_escucha(self):
        fake = "  sl local_address rem_address st tx_rx\n"
        fake += "   0: 00000000:0016 00000000:0000 0A 00000000:00000000\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=fake)):
            sockets = security._listening_sockets()
        self.assertEqual(sockets, [("tcp", 22)])

    def test_sync_pacman_inexistente(self):
        with mock.patch.object(Path, "stat", side_effect=OSError):
            self.assertIsNone(security._pacman_sync_age_days())


class WriteReportTest(unittest.TestCase):
    def test_informe_atomico_con_permisos_600(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "informes" / "audit.json"
            report = {"overall": "ok", "checks": []}
            out = write_report(report, path)
            self.assertEqual(out, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), report)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            # sin ficheros temporales huérfanos
            self.assertEqual([p.name for p in path.parent.iterdir()], ["audit.json"])

    def test_agente_guarda_ultima_auditoria(self):
        agent = SecurityAgent()
        report = agent.audit({"vault": {"backend": "memory"}})
        self.assertEqual(agent.recall("last_audit"), report)

    def test_describe_sin_capacidades_ofensivas(self):
        info = SecurityAgent().describe()
        self.assertFalse(info["offensive_capabilities"])
        self.assertIn("defensive_audit_readonly", info["tools"])


if __name__ == "__main__":
    unittest.main()
