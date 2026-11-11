"""Coordinador de agentes: distribución de tareas con permisos y trazabilidad.

Diseño:
  - Un agente solo recibe tareas cuyo modo está registrado y cuya herramienta
    está permitida por la ToolPolicy de su modo.
  - Ningún agente puede concederse permisos a sí mismo: las autorizaciones de
    herramientas sensibles las firma el coordinador con ``user_approved=True``
    y quedan registradas en el historial de actividad.
  - Las comunicaciones usan AgentMessage (contrato estructurado existente).
  - Cada tarea y resultado queda en un historial acotado, consultable.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from nexora.agents.base import AgentMessage, BaseAgent
from nexora.core.permissions import ApprovalRequiredError, ToolPolicy
from nexora.core.registry import ModeRegistry


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    mode: str
    tool: str
    purpose: str
    payload: Dict[str, Any] = field(default_factory=dict)
    user_approved: bool = False


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    mode: str
    status: str            # ok | denied | error
    detail: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class Coordinator:
    def __init__(self, registry: Optional[ModeRegistry] = None, history_size: int = 200):
        self.registry = registry or ModeRegistry()
        self._agents: Dict[str, BaseAgent] = {}
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_size)
        self._task_seq = 0

    # -- agentes ------------------------------------------------------------
    def agent_for(self, mode: str) -> BaseAgent:
        if mode not in self._agents:
            self._agents[mode] = self.registry.create_agent(mode)
        return self._agents[mode]

    def agents(self) -> Dict[str, Dict[str, Any]]:
        return {mode: agent.describe() for mode, agent in sorted(self._agents.items())}

    # -- tareas -------------------------------------------------------------
    def submit(self, tool_request: str, mode: str, purpose: str,
               payload: Optional[Dict[str, Any]] = None, user_approved: bool = False) -> AgentResult:
        """Registra y valida una tarea. Nunca ejecuta herramientas sensibles sin aprobación."""
        self._task_seq += 1
        task = AgentTask(
            task_id=f"task-{self._task_seq:04d}",
            mode=mode,
            tool=tool_request,
            purpose=purpose,
            payload=dict(payload or {}),
            user_approved=bool(user_approved),
        )
        try:
            result = self._dispatch(task)
        except Exception as exc:  # una tarea defectuosa no derriba el coordinador
            result = AgentResult(task.task_id, mode, "error", f"{type(exc).__name__}: {exc}")
        self._history.append({
            "task_id": task.task_id, "mode": mode, "tool": tool_request,
            "purpose": purpose, "user_approved": task.user_approved,
            "status": result.status, "detail": result.detail,
        })
        return result

    def _dispatch(self, task: AgentTask) -> AgentResult:
        if not self.registry.is_valid(task.mode):
            return AgentResult(task.task_id, task.mode, "denied", f"modo desconocido: {task.mode}")
        if not task.purpose or not task.purpose.strip():
            return AgentResult(task.task_id, task.mode, "denied", "tarea sin propósito declarado")

        policy = self.registry.tool_policy(task.mode)
        if not policy.may_use(task.tool):
            return AgentResult(task.task_id, task.mode, "denied",
                               f"la herramienta '{task.tool}' no está permitida en el modo '{task.mode}'")
        if policy.requires_approval(task.tool) and not task.user_approved:
            raise ApprovalRequiredError(
                f"la herramienta '{task.tool}' requiere aprobación explícita del usuario"
            )

        agent = self.agent_for(task.mode)
        # El agente ejecuta dentro de su ámbito; el coordinador nunca le pasa
        # permisos adicionales ni le permite modificar la política.
        output = agent.process_prompt(task.purpose)
        return AgentResult(task.task_id, task.mode, "ok", "tarea ejecutada en el ámbito del agente",
                           {"output": output})

    # -- comunicación entre agentes -----------------------------------------
    def route_message(self, source_mode: str, dest_mode: str, keys: List[str],
                      purpose: str, user_approved: bool = False) -> AgentMessage:
        """Encamina datos entre agentes con el contrato AgentMessage existente."""
        src, dst = self.agent_for(source_mode), self.agent_for(dest_mode)
        msg = src.share_with(dst, keys, purpose, user_approved=user_approved)
        self._history.append({
            "task_id": f"msg-{len(self._history) + 1}", "mode": source_mode,
            "tool": "share_with", "purpose": purpose, "user_approved": user_approved,
            "status": "ok", "detail": f"datos enviados a {dest_mode}: {list(keys)}",
        })
        return msg

    # -- observación ---------------------------------------------------------
    def history(self) -> tuple:
        return tuple(self._history)

    def status(self) -> Dict[str, Any]:
        denied = sum(1 for h in self._history if h["status"] == "denied")
        errors = sum(1 for h in self._history if h["status"] == "error")
        return {
            "agents": sorted(self._agents),
            "tasks_total": len(self._history),
            "denied": denied,
            "errors": errors,
        }
