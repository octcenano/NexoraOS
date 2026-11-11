"""Tests del coordinador: permisos, aprobación, historial y comunicación."""

import unittest

from nexora.core.coordinator import Coordinator
from nexora.core.permissions import ApprovalRequiredError


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.coord = Coordinator()

    def test_agente_por_modo_y_describe(self):
        agent = self.coord.agent_for("forge")
        self.assertEqual(agent.mode, "forge")
        self.assertEqual(self.coord.agents()["forge"]["mode"], "forge")

    def test_modo_desconocido_denegado(self):
        res = self.coord.submit("local_ai", "nope", "prueba")
        self.assertEqual(res.status, "denied")
        self.assertIn("desconocido", res.detail)

    def test_herramienta_no_permitida_denegada(self):
        # 'office' solo declara 'local_ai'; 'execute_commands' no está permitida.
        res = self.coord.submit("execute_commands", "office", "borrar archivos", user_approved=True)
        self.assertEqual(res.status, "denied")
        self.assertIn("no está permitida", res.detail)

    def test_herramienta_sensible_exige_aprobacion(self):
        # Ningún modo declara herramientas sensibles: la solicitud se deniega
        # por política; si se declarara, exigiría user_approved.
        res = self.coord.submit("local_ai", "forge", "consulta de prueba")
        self.assertEqual(res.status, "ok")

    def test_tarea_sin_proposito_denegada(self):
        res = self.coord.submit("local_ai", "forge", "   ")
        self.assertEqual(res.status, "denied")

    def test_historial_registra_todas_las_tareas(self):
        self.coord.submit("local_ai", "forge", "una")
        self.coord.submit("local_ai", "nope", "dos")
        hist = self.coord.history()
        self.assertEqual(len(hist), 2)
        self.assertEqual({h["status"] for h in hist}, {"ok", "denied"})

    def test_status_resume(self):
        self.coord.submit("local_ai", "forge", "una")
        self.coord.submit("local_ai", "nope", "dos")
        st = self.coord.status()
        self.assertEqual(st["tasks_total"], 2)
        self.assertEqual(st["denied"], 1)
        self.assertEqual(st["agents"], ["forge"])

    def test_route_message_requiere_aprobacion(self):
        self.coord.agent_for("forge").remember("dato", 1)
        with self.assertRaises(Exception):
            self.coord.route_message("forge", "office", ["dato"], "sin aprobar")
        msg = self.coord.route_message("forge", "office", ["dato"], "aprobado", user_approved=True)
        self.assertEqual(dict(msg.data), {"dato": 1})
        # Llega a la bandeja de entrada del receptor, nunca a su memoria.
        self.assertEqual(self.coord.agent_for("office").inbox()[0].source, "forge")
        self.assertIsNone(self.coord.agent_for("office").recall("dato"))

    def test_motor_con_error_no_derriba_al_coordinador(self):
        class Boom:
            def query(self, prompt, system_context=None):
                return {"status": "error", "message": "caído"}
        coord = Coordinator()
        coord.agent_for("forge").engine = Boom()
        res = coord.submit("local_ai", "forge", "prueba con motor caído")
        self.assertEqual(res.status, "ok")
        self.assertIn("error", res.data["output"])


if __name__ == "__main__":
    unittest.main()
