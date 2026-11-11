"""Proveedor local de modelos IA.

Backends:
  - ``local_mock``: respuesta simulada para desarrollo/pruebas (marcada ``simulated: True``).
  - ``ollama``: API nativa de Ollama (``/api/chat``).
  - ``llamacpp`` y ``localai``: API compatible con OpenAI (``/v1/chat/completions``).

Privacidad: por defecto solo se aceptan endpoints de loopback (127.0.0.0/8, ::1,
localhost). Un endpoint remoto exige ``allow_remote=True`` de forma explÃ­cita.
No se registran prompts ni respuestas.
"""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional

BACKENDS = {
    "local_mock": None,
    "ollama": "http://127.0.0.1:11434",
    "llamacpp": "http://127.0.0.1:8080",
    "localai": "http://127.0.0.1:8080",
}


class EngineConnectionError(RuntimeError):
    pass


def _is_loopback(endpoint: str) -> bool:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _http_json(method: str, url: str, payload: Optional[dict], timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # conexiÃ³n directa, sin proxies
    try:
        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise EngineConnectionError(str(exc)) from exc


class LocalAIEngine:
    def __init__(
        self,
        backend: str = "local_mock",
        model: str = "nexora-local-q4",
        endpoint: Optional[str] = None,
        timeout: float = 60.0,
        allow_remote: bool = False,
        transport: Optional[Callable[[str, str, Optional[dict], float], dict]] = None,
    ):
        if backend not in BACKENDS:
            raise ValueError(f"Backend desconocido: {backend}. Opciones: {sorted(BACKENDS)}")
        self.backend = backend
        self.model = model
        self.timeout = timeout
        self._transport = transport or _http_json
        self._reachable = backend == "local_mock"

        default = BACKENDS[backend]
        self.endpoint = (endpoint or default or "").rstrip("/") or None
        if self.endpoint and not allow_remote and not _is_loopback(self.endpoint):
            raise ValueError(
                f"Endpoint no local rechazado: {self.endpoint}. Usa allow_remote=True si es intencionado."
            )

    @property
    def simulated(self) -> bool:
        return self.backend == "local_mock"

    @property
    def is_connected(self) -> bool:
        """Mock: siempre True. Real: resultado de la Ãºltima comprobaciÃ³n o consulta."""
        return self._reachable

    def ping(self) -> bool:
        if self.simulated:
            return True
        path = "/api/tags" if self.backend == "ollama" else "/v1/models"
        try:
            self._transport("GET", self.endpoint + path, None, min(self.timeout, 5.0))
            self._reachable = True
        except EngineConnectionError:
            self._reachable = False
        return self._reachable

    def query(self, prompt: str, system_context: Optional[str] = None) -> Dict[str, Any]:
        """Inferencia en el Ã¡mbito del agente que llama. Nunca lanza por fallos de red."""
        if not isinstance(prompt, str) or not prompt.strip():
            return {"status": "error", "message": "El prompt estÃ¡ vacÃ­o", "backend": self.backend}

        if self.simulated:
            shown = prompt[:30] + ("â¦" if len(prompt) > 30 else "")
            return {
                "status": "success",
                "model": self.model,
                "backend": self.backend,
                "simulated": True,
                "output": f"[{self.model} Â· respuesta simulada] Prompt recibido: '{shown}' (modo aislado).",
            }

        messages = []
        if system_context:
            messages.append({"role": "system", "content": system_context})
        messages.append({"role": "user", "content": prompt})

        try:
            if self.backend == "ollama":
                raw = self._transport(
                    "POST", self.endpoint + "/api/chat",
                    {"model": self.model, "messages": messages, "stream": False}, self.timeout,
                )
                text = raw["message"]["content"]
            else:
                raw = self._transport(
                    "POST", self.endpoint + "/v1/chat/completions",
                    {"model": self.model, "messages": messages}, self.timeout,
                )
                text = raw["choices"][0]["message"]["content"]
        except EngineConnectionError as exc:
            self._reachable = False
            return {"status": "error", "message": f"Backend no disponible: {exc}", "backend": self.backend}
        except (KeyError, IndexError, TypeError):
            return {"status": "error", "message": "Respuesta inesperada del backend", "backend": self.backend}

        self._reachable = True
        return {"status": "success", "model": self.model, "backend": self.backend, "simulated": False, "output": text}


def engine_from_config(cfg: dict) -> LocalAIEngine:
    ai = cfg.get("ai_engine", {})
    endpoint = ai.get("endpoint") or cfg.get("local_model_endpoint") or None
    return LocalAIEngine(
        backend=ai.get("backend", "local_mock"),
        model=ai.get("model", "nexora-local-q4"),
        endpoint=endpoint,
        allow_remote=bool(ai.get("allow_remote", False)),
    )
