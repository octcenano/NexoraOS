"""Permisos explícitos y revocables por conector, y política de herramientas.

Principios:
  - Permiso mínimo: un agente solo usa herramientas declaradas para su modo.
  - Operaciones sensibles (red externa, ejecutar comandos, escribir fuera del
    proyecto, tocar la memoria de otro agente) exigen aprobación explícita.
  - Nada aquí modifica políticas automáticamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Permission:
    connector: str
    scopes: tuple[str, ...]
    granted: bool = False


def may_access(permission: Permission, scope: str) -> bool:
    """Solo con permiso concedido y el scope declarado."""
    return permission.granted and scope in permission.scopes


class ApprovalRequiredError(PermissionError):
    """Operación sensible sin aprobación explícita del usuario."""


# Herramientas que nunca se ejecutan sin aprobación explícita del usuario.
SENSITIVE_TOOLS = frozenset({
    "network_remote",        # enviar datos a servicios externos
    "execute_commands",      # ejecutar comandos del sistema
    "write_system",          # escribir fuera del espacio del proyecto
    "access_other_agent_memory",
})


@dataclass(frozen=True)
class ToolPolicy:
    """Herramientas permitidas por modo y cuáles exigen aprobación."""

    mode: str
    allowed_tools: tuple[str, ...] = ()
    approval_tools: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not self.mode:
            raise ValueError("ToolPolicy necesita un modo")
        object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools))
        object.__setattr__(self, "approval_tools", tuple(self.approval_tools))
        unknown = set(self.approval_tools) - set(self.allowed_tools) - set(SENSITIVE_TOOLS)
        if unknown:
            raise ValueError(f"Herramientas de aprobación no declaradas como permitidas: {sorted(unknown)}")

    def may_use(self, tool: str) -> bool:
        return tool in self.allowed_tools

    def requires_approval(self, tool: str) -> bool:
        return tool in SENSITIVE_TOOLS or tool in self.approval_tools

    def authorize_use(self, tool: str, user_approved: bool = False) -> None:
        """Autoriza una herramienta o lanza ApprovalRequiredError."""
        if not self.may_use(tool):
            raise PermissionError(f"La herramienta '{tool}' no está permitida en el modo '{self.mode}'")
        if self.requires_approval(tool) and not user_approved:
            raise ApprovalRequiredError(
                f"La herramienta '{tool}' requiere aprobación explícita del usuario"
            )
