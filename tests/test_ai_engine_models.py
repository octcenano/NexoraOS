import unittest

from nexora.core.ai_engine import EngineConnectionError, LocalAIEngine


def fake_transport_ollama(method, url, payload, timeout):
    if method == "GET" and url.endswith("/api/tags"):
        return {"models": [{"name": "llama3.2:q4"}, {"name": "qwen2.5:7b"}, {"bad": 1}]}
    raise EngineConnectionError("no")


def fake_transport_openai(method, url, payload, timeout):
    if method == "GET" and url.endswith("/v1/models"):
        return {"data": [{"id": "model-a"}, {"id": "model-b"}, {"nope": True}]}
    raise EngineConnectionError("no")


def failing_transport(method, url, payload, timeout):
    raise EngineConnectionError("conexión rechazada")


class ListModelsTests(unittest.TestCase):
    def test_ollama_lists_model_names(self):
        e = LocalAIEngine("ollama", endpoint="http://127.0.0.1:11434", transport=fake_transport_ollama)
        res = e.list_models()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["models"], ["llama3.2:q4", "qwen2.5:7b"])
        self.assertFalse(res["simulated"])
        self.assertTrue(e.is_connected)

    def test_openai_compatible_lists_model_ids(self):
        for backend in ("llamacpp", "localai"):
            e = LocalAIEngine(backend, endpoint="http://127.0.0.1:8080", transport=fake_transport_openai)
            res = e.list_models()
            self.assertEqual(res["models"], ["model-a", "model-b"])

    def test_unreachable_backend_returns_error_not_exception(self):
        e = LocalAIEngine("ollama", endpoint="http://127.0.0.1:9", transport=failing_transport)
        res = e.list_models()
        self.assertEqual(res["status"], "error")
        self.assertFalse(e.is_connected)

    def test_mock_is_labelled_simulated(self):
        e = LocalAIEngine()
        res = e.list_models()
        self.assertTrue(res["simulated"])
        self.assertEqual(res["models"], [e.model])


if __name__ == "__main__":
    unittest.main()
