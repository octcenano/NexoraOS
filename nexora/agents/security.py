"""Agente del modo Security: auditoría defensiva de solo lectura.

Alcance deliberado: diagnóstico y auditoría en sistemas autorizados. No hay
escaneo de red, no hay explotación, no hay automatizaciones de intrusión.
Todas las comprobaciones leen estado local y no modifican nada. La única
escritura posible es un informe explícito solicitado por el usuario
(``write_report``), en la ruta que el usuario indique.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nexora.agents.base import BaseAgent


def _listening_sockets() -> Optional[List[Tuple[str, int]]]:
    """Inventario de sockets en escucha (IPv4/IPv6) leyendo /proc. None si no hay datos."""
    sockets: List[Tuple[str, int]] = []
    found_any = False
    for path, family in (("/proc/net/tcp", "tcp"), ("/proc/net/tcp6", "tcp6")):
        try:
            with open(path, encoding="ascii") as fh:
                next(fh)  # cabecera
                for line in fh:
                    parts = line.split()
                    if len(parts) > 3 and parts[3] == "0A":  # TCP_LISTEN
                        port = int(parts[1].split(":")[1], 16)
                        sockets.append((family, port))
                        found_any = True
        except (OSError, ValueError):
            continue
    return sorted(set(sockets)) if found_any else None


def _pacman_sync_age_days() -> Optional[float]:
    """Días desde la última sincronización de pacman (solo lectura)."""
    db = Path("/var/lib/pacman/sync/core.db")
    try:
        mtime = os.stat(db).st_mtime
    except OSError:
        return None
    return round((time.time() - mtime) / 86400, 1)


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

    sockets = _listening_sockets()
    if sockets is None:
        checks.append({"name": "listening_sockets", "status": "warn", "detail": "no disponible en este sistema"})
    else:
        detail = ", ".join(f"{f}:{p}" for f, p in sockets) or "ninguno"
        checks.append({"name": "listening_sockets", "status": "ok",
                       "detail": f"{len(sockets)} socket(s) en escucha [{detail}] (informativo)"})

    age = _pacman_sync_age_days()
    if age is None:
        checks.append({"name": "updates", "status": "warn",
                       "detail": "no se pudo leer /var/lib/pacman/sync (¿no es Arch o sin permisos?)"})
    elif age > 14:
        checks.append({"name": "updates", "status": "warn",
                       "detail": f"última sincronización de pacman hace {age} días; ejecuta 'sudo pacman -Syu'"})
    else:
        checks.append({"name": "updates", "status": "ok",
                       "detail": f"última sincronización de pacman hace {age} días"})

    nexora_dirs = [Path.home() / ".config" / "nexora"]
    ww = _world_writable_in(nexora_dirs)
    checks.append({"name": "world_writable_files", "status": "ok" if not ww else "warn",
                   "detail": "ninguno" if not ww else f"{len(ww)} archivo(s) escribibles por otros"})

    overall = "fail" if any(c["status"] == "fail" for c in checks) else \
              "warn" if any(c["status"] == "warn" for c in checks) else "ok"

    recommendations: List[str] = []
    for c in checks:
        if c["status"] == "fail":
            recommendations.append(f"[{c['name']}] {c['detail']} — corrígelo antes de continuar.")
        elif c["status"] == "warn":
            recommendations.append(f"[{c['name']}] {c['detail']}")

    return {"overall": overall, "checks": checks, "recommendations": recommendations,
            "scope": "read_only_defensive"}


def write_report(report: Dict[str, Any], path: Path) -> Path:
    """Escribe el informe de auditoría en la ruta indicada por el usuario.

    Única escritura del agente Security: explícita, atómica y con permisos 600.
    Nunca se ejecuta automáticamente.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".audit-", suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


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
        info["tools"] = ["defensive_audit_readonly", "write_report_explicit"]
        info["offensive_capabilities"] = False
        return info
