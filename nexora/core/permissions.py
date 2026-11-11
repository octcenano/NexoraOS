"""Permisos explÃ­citos y revocables por conector."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    connector: str
    scopes: tuple[str, ...]
    granted: bool = False


def may_access(permission: Permission, scope: str) -> bool:
    """Solo con permiso concedido y el scope declarado."""
    return permission.granted and scope in permission.scopes
