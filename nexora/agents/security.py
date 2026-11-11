"""Agente del modo Security: auditoría defensiva de solo lectura.

Alcance deliberado: diagnóstico y auditoría en sistemas autorizados. No hay
escaneo de red, no hay explotación, no hay automatizaciones de intrusión.
Todas las comprobaciones leen estado local y no modifican nada.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional

from nexora.agents.base import BaseAgent


def _listening_socket_count() -> Optional[int]:
    """Cuenta sockets en escucha (IPv4/IPv6) leyendo /proc. None si no hay datos."""
    count = 0
    found_any = False
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path, encoding="ascii") as fh:
                next(fh)  # cabecera
                for line in fh:
                    parts = line.split()
                    if len(parts) > 3 and parts[3] == "0A":  # TCP_LISTEN
                        count += 1
                        found_any = True
        except OSError:
            continue
    return count if found_any else None


def _config_file_permissions() -> Optional[str]:
    """Permisos del user.json si existe; None si no hay archivo."""
    from nexora.core.config import default_user_config_path

    path = default_user_config_path()
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return None
    return oct(mode)


def _world_writable_in(paths: List[Path], limit: int = 50) -> List[str]:
    """Ficheros escribibles por 'otros' bajo las rutas dadas (solo lectura)."""
    found: List[str] = []
    for base in paths:
        if not base.is_dir():
            continue
        for root, dirs, files in os.walk(base):
            for name in files:
                p = Path(root) / name
                try:
                    if stat.S_IMODE(os.stat(p).st_mode) & stat.S_IWOTH:
                        found.append(str(p))
                except OSError:
                    continue
                if len(found) >= limit:
                    return found
    return found


def run_defensive_audit(cfg: Optional[dict] = None) -> Dict[str, Any]:
    """Auditoría defensiva local y de solo lectura. No requiere privilegios."""
    from nexora.core.config import load_config, find_secret_like
    from nexora.core.vault import vault_from_config, VaultUnavailableError

    checks: List[Dict[str, Any]] = []

    try:
        cfg = cfg or load_config()
        checks.append({"name": "config", "status": "ok", "detail": f"válida, versión {cfg.get('version')}"})
        secrets = find_secret_like(cfg)
        checks.append({"name": "config_secrets", "status": "ok" if not secrets else "fail",
                       "detail": "sin secretos en configuración" if not secrets else str(secrets)})
    except Exception as exc:
        checks.append({"name": "config", "status": "fail", "detail": str(exc)})
        cfg = None

    if cfg:
        try:
            vault = vault_from_config(cfg)
            checks.append({"name": "vault", "status": "ok",
                           "detail": f"backend {vault.backend_name} (persistente: {vault.persistent})"})
        except VaultUnavailableError as exc:
            checks.append({"name": "vault", "status": "warn", "detail": str(exc)})

    perms = _config_file_permissions()
    if perms is None:
        checks.append({"name": "user_config_permissions", "status": "ok", "detail": "sin user.json (nada que proteger)"})
    elif perms in ("0o600", "0o400"):
        checks.append({"name": "user_config_permissions", "status": "ok", "detail": f"permisos {perms}"})
    else:
        checks.append({"name": "user_config_permissions", "status": "warn",
                       "detail": f"permisos {perms}; se recomienda 600 (chmod 600)"})

    sockets = _listening_socket_count()
    if sockets is None:
        checks.append({"name": "listening_sockets", "status": "warn", "detail": "no disponible en este sistema"})
    else:
        checks.append({"name": "listening_sockets", "status": "ok",
                       "detail": f"{sockets} socket(s) en escucha (informativo, revísalos tú)"})

    nexora_dirs = [Path.home() / ".config" / "nexora"]
    ww = _world_writable_in(nexora_dirs)
    checks.append({"name": "world_writable_files", "status": "ok" if not ww else "warn",
                   "detail": "ninguno" if not ww else f"{len(ww)} archivo(s) escribibles por otros"})

    overall = "fail" if any(c["status"] == "fail" for c in checks) else \
              "warn" if any(c["status"] == "warn" for c in checks) else "ok"
    return {"overall": overall, "checks": checks, "scope": "read_only_defensive"}


class SecurityAgent(BaseAgent):
    """Modo Security: auditoría defensiva de solo lectura en sistemas autorizados."""

    status = "basic"

    def __init__(self, engine=None):
        super().__init__(
            name="SecurityAgent",
            mode="security",
            engine=engine,
            system_context="Modo Security: auditoría defensiva de solo lectura",
        )

    def audit(self, cfg: Optional[dict] = None) -> Dict[str, Any]:
        report = run_defensive_audit(cfg)
        self.remember("last_audit", report)
        return report

    def describe(self) -> dict:
        info = super().describe()
        info["tools"] = ["defensive_audit_readonly"]
        info["offensive_capabilities"] = False
        return info
