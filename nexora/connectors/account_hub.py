"""Account Hub: catÃ¡logo de conexiones aprobadas por el usuario.

Nunca guarda secretos. Si una conexiÃ³n necesita credenciales, solo se anota
``secret_ref``: el nombre de la entrada en ``nexora.core.vault``.

Esta versiÃ³n implementa el ciclo de vida y los permisos. NO implementa OAuth
real: ``grant()`` es el punto donde la UI registrarÃ¡ el consentimiento del
usuario una vez completado un flujo oficial.
"""

from __future__ import annotations

from typing import Iterable, Optional

from nexora.core.permissions import Permission, may_access

NOT_CONFIGURED = "not_configured"
PENDING = "pending_authorization"
CONNECTED = "connected"
EXPIRED = "expired"
REVOKED = "revoked"
ERROR = "error"
STATES = (NOT_CONFIGURED, PENDING, CONNECTED, EXPIRED, REVOKED, ERROR)


class AccountHub:
    def __init__(self):
        self._connections: dict = {}

    # -- alta -------------------------------------------------------------
    def register_connection(
        self,
        service: str,
        connector_type: str,
        scopes: Iterable[str] = (),
        secret_ref: Optional[str] = None,
    ) -> None:
        """Registra (o reinicia) una conexiÃ³n. Siempre queda sin autorizar."""
        if not service or not connector_type:
            raise ValueError("service y connector_type son obligatorios")
        self._connections[service] = {
            "connector_type": connector_type,
            "scopes": tuple(scopes),
            "state": PENDING,
            "secret_ref": secret_ref,
        }

    # -- transiciones -----------------------------------------------------
    def grant(self, service: str) -> None:
        """Consentimiento explÃ­cito del usuario. Solo desde pending_authorization."""
        conn = self._get(service)
        if conn["state"] != PENDING:
            raise ValueError(
                f"No se puede autorizar '{service}' desde el estado '{conn['state']}'; "
                "vuelve a registrar la conexiÃ³n"
            )
        conn["state"] = CONNECTED

    def revoke(self, service: str) -> None:
        self._get(service)["state"] = REVOKED

    def mark_expired(self, service: str) -> None:
        conn = self._get(service)
        if conn["state"] != CONNECTED:
            raise ValueError("Solo una conexiÃ³n 'connected' puede expirar")
        conn["state"] = EXPIRED

    def mark_error(self, service: str) -> None:
        self._get(service)["state"] = ERROR

    # -- consulta ---------------------------------------------------------
    def get_state(self, service: str) -> str:
        conn = self._connections.get(service)
        return conn["state"] if conn else NOT_CONFIGURED

    def is_authorized(self, service: str) -> bool:
        return self.get_state(service) == CONNECTED

    def may_access(self, service: str, scope: str) -> bool:
        conn = self._connections.get(service)
        if conn is None:
            return False
        perm = Permission(service, conn["scopes"], granted=conn["state"] == CONNECTED)
        return may_access(perm, scope)

    def list_connections(self) -> dict:
        return {k: dict(v) for k, v in self._connections.items()}

    def summary(self) -> str:
        states = {c["state"] for c in self._connections.values()}
        if CONNECTED in states:
            return "connected"
        if PENDING in states:
            return PENDING
        return "disconnected"

    def _get(self, service: str) -> dict:
        try:
            return self._connections[service]
        except KeyError:
            raise KeyError(f"ConexiÃ³n desconocida: {service}") from None
