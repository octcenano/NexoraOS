"""Frontera mÃ­nima de agente: memoria privada por modo y mensajes explÃ­citos.

Aviso de alcance: el aislamiento es LÃGICO (espacio de nombres y API). No hay
aislamiento de procesos ni sandbox todavÃ­a; eso pertenece a Beta 0.3+.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional


@dataclass(frozen=True)
class AgentMessage:
    """Contrato de intercambio entre agentes: origen, destino, propÃ³sito y datos."""

    source: str
    destination: str
    purpose: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.purpose or not self.purpose.strip():
            raise ValueError("El mensaje necesita un propÃ³sito")
        if self.source == self.destination:
            raise ValueError("Origen y destino deben ser modos distintos")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


class BaseAgent:
    status = "stub"

    def __init__(self, name: str, mode: str, engine=None, system_context: Optional[str] = None):
        if not name or not mode:
            raise ValueError("name y mode son obligatorios")
        self.name = name
        self.mode = mode
        self.engine = engine
        self.system_context = system_context or f"Modo {mode} aislado"
        self.memory_namespace = f"agents/{mode}/"
        self._memory: dict = {}
        self._inbox: list = []

    # -- memoria privada --------------------------------------------------
    def remember(self, key: str, value: Any) -> None:
        self._memory[key] = deepcopy(value)

    def recall(self, key: str, default: Any = None) -> Any:
        return deepcopy(self._memory.get(key, default))

    def forget(self, key: str) -> bool:
        return self._memory.pop(key, None) is not None

    def memory_keys(self) -> tuple:
        return tuple(self._memory)

    # -- intercambio explÃ­cito -------------------------------------------
    def share_with(
        self,
        other: "BaseAgent",
        keys: Iterable[str],
        purpose: str,
        user_approved: bool = False,
    ) -> AgentMessage:
        """EnvÃ­a datos seleccionados a otro agente. Requiere aprobaciÃ³n del usuario.

        Los datos llegan a la bandeja de entrada del receptor, nunca a su
        memoria privada.
        """
        if not user_approved:
            raise PermissionError("Compartir datos entre modos requiere aprobaciÃ³n explÃ­cita del usuario")
        keys = tuple(keys)
        missing = [k for k in keys if k not in self._memory]
        if missing:
            raise KeyError(f"Claves inexistentes en la memoria de {self.mode}: {missing}")
        msg = AgentMessage(
            source=self.mode,
            destination=other.mode,
            purpose=purpose,
            data={k: deepcopy(self._memory[k]) for k in keys},
        )
        other.receive(msg)
        return msg

    def receive(self, message: AgentMessage) -> None:
        if message.destination != self.mode:
            raise ValueError(f"Mensaje dirigido a '{message.destination}', no a '{self.mode}'")
        self._inbox.append(message)

    def inbox(self) -> tuple:
        return tuple(self._inbox)

    # -- informaciÃ³n e inferencia ----------------------------------------
    def describe(self) -> dict:
        return {
            "name": self.name,
            "mode": self.mode,
            "memory_namespace": self.memory_namespace,
            "shared_private_memory": False,
            "status": self.status,
        }

    def process_prompt(self, prompt: str) -> str:
        if self.engine is None:
            return f"{self.name} [{self.mode}]: {prompt}"
        res = self.engine.query(prompt, system_context=self.system_context)
        if res.get("status") != "success":
            return f"[error] {res.get('message', 'fallo desconocido del motor IA')}"
        return res["output"]
