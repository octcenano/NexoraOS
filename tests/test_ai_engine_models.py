"""Tests del motor IA local: select_model, has_model, list_models y detect_backends."""

import unittest

from nexora.core.ai_engine import (
    EngineConnectionError,
    LocalAIEngine,
    _is_loopback,
    detect_backends,
)


class FakeTransport:
    """Transporte falso para backends HTTP sin red real."""

    def __init__(self, models=None, fail=False):
        self.models = models if models is not None else [{"id": "qwen2.5:3b"}]
        self.fail = fail
        self.calls = []

    def __call__(self, method, url, payload, timeout):
        self.calls.append((method, url, payload, timeout))
        if self.fail:
            raise EngineConnectionError("conexión rechazada")
        if url.endswith("/api/tags"):
            return {"models": [{"name": m["id"]} for m in self.models]}
        if url.endswith("/v1/models"):
            return {"data": self.models}
        if url.endswith("/api/chat"):
            return {"message": {"content": "hola desde ollama"}}
        if url.endswith("/v1/chat/completions"):
            return {"choices": [{"message": {"content": "hola desde openai-compat"}}]}
        raise EngineConnectionError(f"url inesperada: {url}")


class LoopbackTest(unittest.TestCase):
    def test_loopback_aceptado(self):
        for ep in ("http://127.0.0.1:11434", "http://localhost:8080", "http://[::1]:1234"):
            self.assertTrue(_is_loopback(ep), ep)

    def test_remoto_rechazado_por_defecto(self):
        with self.assertRaises(ValueError):
            LocalAIEngine(backend="ollama", endpoint="http://10.0.0.5:11434")

    def test_remoto_con_consentimiento(self):
        eng = LocalAIEngine(backend="ollama", endpoint="http://10.0.0.5:11434", allow_remote=True)
        self.assertEqual(eng.endpoint, "http://10.0.0.5:11434")


class MockEngineTest(unittest.TestCase):
    def test_mock_simulado_y_conectado(self):
        eng = LocalAIEngine()
        self.assertTrue(eng.simulated)
        self.assertTrue(eng.is_connected)
        res = eng.query("hola")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["simulated"])

    def test_mock_lista_su_modelo(self):
        eng = LocalAIEngine(model="nexora-local-q4")
        res = eng.list_models()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["models"], ["nexora-local-q4"])
        self.assertTrue(res["simulated"])

    def test_prompt_vacio(self):
        eng = LocalAIEngine()
        res = eng.query("   ")
        self.assertEqual(res["status"], "error")


class RealBackendTest(unittest.TestCase):
    def test_select_model(self):
        eng = LocalAIEngine(backend="ollama", transport=FakeTransport())
        eng.select_model("  llama3.2:1b ")
        self.assertEqual(eng.model, "llama3.2:1b")
        with self.assertRaises(ValueError):
            eng.select_model("   ")

    def test_list_models_ollama(self):
        ft = FakeTransport(models=[{"id": "llama3.2:1b"}, {"id": "qwen2.5:3b"}])
        eng = LocalAIEngine(backend="ollama", transport=ft)
        res = eng.list_models()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["models"], ["llama3.2:1b", "qwen2.5:3b"])
        self.assertFalse(res["simulated"])

    def test_list_models_openai_compat(self):
        ft = FakeTransport(models=[{"id": "gpt-4o-mini-local"}])
        eng = LocalAIEngine(backend="localai", transport=ft)
        res = eng.list_models()
        self.assertEqual(res["models"], ["gpt-4o-mini-local"])

    def test_has_model(self):
        eng = LocalAIEngine(backend="ollama", transport=FakeTransport(models=[{"id": "llama3.2:1b"}]))
        self.assertTrue(eng.has_model("llama3.2:1b"))
        self.assertFalse(eng.has_model("no-existe"))

    def test_backend_caido(self):
        ft = FakeTransport(fail=True)
        eng = LocalAIEngine(backend="ollama", transport=ft)
        self.assertFalse(eng.ping())
        self.assertFalse(eng.is_connected)
        res = eng.list_models()
        self.assertEqual(res["status"], "error")
        self.assertIn("no disponible", res["message"])
        res = eng.query("hola")
        self.assertEqual(res["status"], "error")
        self.assertFalse(eng.has_model("llama3.2:1b"))

    def test_query_ollama(self):
        ft = FakeTransport()
        eng = LocalAIEngine(backend="ollama", transport=ft)
        res = eng.query("hola", system_context="ctx")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["output"], "hola desde ollama")
        method, url, payload, _ = ft.calls[-1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/api/chat"))
        self.assertEqual(payload["model"], eng.model)
        self.assertFalse(payload["stream"])

    def test_query_openai_compat(self):
        ft = FakeTransport()
        eng = LocalAIEngine(backend="llamacpp", transport=ft)
        res = eng.query("hola")
        self.assertEqual(res["status"], "success")
        method, url, _, _ = ft.calls[-1]
        self.assertTrue(url.endswith("/v1/chat/completions"))

    def test_respuesta_inesperada_no_lanza(self):
        class Weird:
            def __call__(self, method, url, payload, timeout):
                return {"inesperado": True}
        eng = LocalAIEngine(backend="ollama", transport=Weird())
        res = eng.query("hola")
        self.assertEqual(res["status"], "error")
        self.assertIn("inesperada", res["message"])


class DetectBackendsTest(unittest.TestCase):
    def test_sin_backends_reales(self):
        res = detect_backends(transport=FakeTransport(fail=True))
        self.assertEqual(set(res), {"ollama", "llamacpp", "localai"})
        for info in res.values():
            self.assertFalse(info["available"])
            self.assertEqual(info["models"], [])

    def test_con_ollama_activo(self):
        def transport(method, url, payload, timeout):
            if url.startswith("http://127.0.0.1:11434"):
                return {"models": [{"name": "llama3.2:1b"}]}
            raise EngineConnectionError("no hay nada aquí")

        res = detect_backends(transport=transport)
        self.assertTrue(res["ollama"]["available"])
        self.assertEqual(res["ollama"]["models"], ["llama3.2:1b"])
        self.assertFalse(res["localai"]["available"])

    def test_no_consulta_endpoints_remotos(self):
        seen = []

        def transport(method, url, payload, timeout):
            seen.append(url)
            raise EngineConnectionError("x")

        detect_backends(transport=transport)
        for url in seen:
            self.assertIn("127.0.0.1", url)


if __name__ == "__main__":
    unittest.main()
