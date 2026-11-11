import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from nexora.core.ai_engine import LocalAIEngine, engine_from_config


class _Handler(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):  # silencio
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": []})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.seen.append((self.path, payload))
        if self.path == "/api/chat":
            self._send({"message": {"role": "assistant", "content": "hola desde ollama"}})
        elif self.path == "/v1/chat/completions":
            self._send({"choices": [{"message": {"role": "assistant", "content": "hola desde openai-compat"}}]})
        else:
            self._send({"weird": True})


class RealHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _Handler.seen.clear()

    def test_ollama(self):
        e = LocalAIEngine("ollama", model="m", endpoint=self.url)
        self.assertFalse(e.is_connected)
        res = e.query("hola", system_context="ctx")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["output"], "hola desde ollama")
        self.assertFalse(res["simulated"])
        path, payload = _Handler.seen[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "ctx"})
        self.assertFalse(payload["stream"])
        self.assertTrue(e.is_connected)

    def test_openai_compatible_backends(self):
        for backend in ("llamacpp", "localai"):
            res = LocalAIEngine(backend, endpoint=self.url).query("hola")
            self.assertEqual(res["output"], "hola desde openai-compat")
            self.assertEqual(_Handler.seen[-1][0], "/v1/chat/completions")

    def test_ping(self):
        self.assertTrue(LocalAIEngine("ollama", endpoint=self.url).ping())

    def test_unexpected_response_shape(self):
        e = LocalAIEngine("ollama", endpoint=self.url, transport=lambda *a: {"weird": True})
        self.assertEqual(e.query("x")["status"], "error")

    def test_unreachable_backend_returns_error_not_exception(self):
        e = LocalAIEngine("ollama", endpoint="http://127.0.0.1:9", timeout=1)  # puerto cerrado
        res = e.query("hola")
        self.assertEqual(res["status"], "error")
        self.assertFalse(e.is_connected)
        self.assertFalse(e.ping())


class EngineRulesTests(unittest.TestCase):
    def test_mock_is_labelled_simulated(self):
        res = LocalAIEngine().query("Hola")
        self.assertTrue(res["simulated"])
        self.assertIn("simulada", res["output"])

    def test_empty_prompt(self):
        self.assertEqual(LocalAIEngine().query("  ")["status"], "error")

    def test_unknown_backend(self):
        with self.assertRaises(ValueError):
            LocalAIEngine("gpt-cloud")

    def test_remote_endpoint_rejected_unless_explicit(self):
        with self.assertRaises(ValueError):
            LocalAIEngine("ollama", endpoint="http://192.168.1.50:11434")
        with self.assertRaises(ValueError):
            LocalAIEngine("ollama", endpoint="https://api.example.com")
        LocalAIEngine("ollama", endpoint="http://192.168.1.50:11434", allow_remote=True)
        LocalAIEngine("ollama", endpoint="http://localhost:11434")
        LocalAIEngine("ollama", endpoint="http://[::1]:11434")

    def test_engine_from_config(self):
        cfg = {"ai_engine": {"backend": "ollama", "model": "x", "endpoint": "", "allow_remote": False},
               "local_model_endpoint": "http://127.0.0.1:5555"}
        e = engine_from_config(cfg)
        self.assertEqual((e.backend, e.model, e.endpoint), ("ollama", "x", "http://127.0.0.1:5555"))


if __name__ == "__main__":
    unittest.main()
