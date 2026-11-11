"""BÃ³veda de secretos.

GarantÃ­a de diseÃ±o: los secretos nunca se escriben en JSON ni en el repositorio.

Backends:
  - ``MemoryBackend`` (por defecto): solo en RAM. No persiste y no hay cifrado
    porque nada llega a disco.
  - ``KeyringBackend``: delega en el almacÃ©n seguro del sistema operativo a
    travÃ©s del paquete opcional ``keyring`` (``pip install keyring``).

No se implementa criptografÃ­a propia.
"""

from __future__ import annotations

from typing import Optional


class VaultUnavailableError(RuntimeError):
    pass


class MemoryBackend:
    name = "memory"
    persistent = False

    def __init__(self):
        self._data: dict = {}

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None


class KeyringBackend:
    name = "os-keyring"
    persistent = True
    SERVICE = "nexora-os"

    def __init__(self, keyring_module=None):
        if keyring_module is None:
            try:
                import keyring as keyring_module  # type: ignore
            except ImportError as exc:
                raise VaultUnavailableError(
                    "El backend 'keyring' requiere el paquete 'keyring' y un almacÃ©n de secretos del SO"
                ) from exc
        self._kr = keyring_module

    def set(self, key: str, value: str) -> None:
        self._kr.set_password(self.SERVICE, key, value)

    def get(self, key: str) -> Optional[str]:
        return self._kr.get_password(self.SERVICE, key)

    def delete(self, key: str) -> bool:
        if self._kr.get_password(self.SERVICE, key) is None:
            return False
        self._kr.delete_password(self.SERVICE, key)
        return True


class SecureVault:
    def __init__(self, backend=None):
        self._backend = backend or MemoryBackend()

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def persistent(self) -> bool:
        return self._backend.persistent

    def set_secret(self, key: str, value: str) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("La clave del secreto no puede estar vacÃ­a")
        if not isinstance(value, str) or not value:
            raise ValueError("El valor del secreto no puede estar vacÃ­o")
        self._backend.set(key, value)

    def get_secret(self, key: str) -> Optional[str]:
        return self._backend.get(key)

    def has_secret(self, key: str) -> bool:
        return self._backend.get(key) is not None

    def revoke_secret(self, key: str) -> bool:
        return self._backend.delete(key)

    def __repr__(self) -> str:  # nunca incluye valores
        return f"SecureVault(backend={self.backend_name!r})"


def vault_from_config(cfg: dict) -> SecureVault:
    if cfg.get("vault", {}).get("backend") == "keyring":
        return SecureVault(KeyringBackend())
    return SecureVault(MemoryBackend())
