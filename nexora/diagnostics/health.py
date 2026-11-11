"""DiagnÃ³stico. ``basic_health`` declara lo que aÃºn no existe; ``health_report`` comprueba lo que sÃ­."""

from __future__ import annotations

import sys
from typing import Optional

from nexora import __version__
from nexora.connectors.browser import BrowserConnector
from nexora.core.ai_engine import engine_from_config
from nexora.core.config import ConfigError, load_config
from nexora.core.registry import ModeRegistry
from nexora.core.vault import vault_from_config, VaultUnavailableError


def basic_health() -> dict:
    return {
        "core": "ok",
        "agent_isolation": "logical_namespaces",
        "browser_connectors": "interfaces_only",
        "watchdogs": "planned_not_running",
        "systemd_daemons": "not_installed",
        "iso_builder": "not_implemented",
    }


def _check(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def _check_isolation() -> dict:
    reg = ModeRegistry()
    modes = reg.names()
    if len(modes) < 2:
        return _check("agent_isolation", "fail", "Se necesitan al menos 2 modos para comprobar aislamiento")
    a, b = reg.create_agent(modes[0]), reg.create_agent(modes[1])
    a.remember("__probe__", "x")
    ok = b.recall("__probe__") is None and not b.memory_keys()
    return _check("agent_isolation", "ok" if ok else "fail",
                  "memoria privada separada entre modos" if ok else "Â¡memoria compartida entre agentes!")


def health_report(cfg: Optional[dict] = None) -> dict:
    checks = []

    py_ok = sys.version_info >= (3, 10)
    checks.append(_check("python", "ok" if py_ok else "fail", f"{sys.version.split()[0]} (se requiere >= 3.10)"))

    if cfg is None:
        try:
            cfg = load_config()
            checks.append(_check("config", "ok", f"vÃ¡lida, versiÃ³n {cfg['version']} = paquete {__version__}"))
        except ConfigError as exc:
            checks.append(_check("config", "fail", str(exc)))
    else:
        checks.append(_check("config", "ok", f"vÃ¡lida, versiÃ³n {cfg.get('version')}"))

    checks.append(_check_isolation())

    if cfg:
        try:
            vault = vault_from_config(cfg)
            kind = "persistente (almacÃ©n del SO)" if vault.persistent else "volÃ¡til (solo RAM, no persiste)"
            checks.append(_check("vault", "ok", f"{vault.backend_name}: {kind}"))
        except VaultUnavailableError as exc:
            checks.append(_check("vault", "fail", str(exc)))

        engine = engine_from_config(cfg)
        if engine.simulated:
            checks.append(_check("ai_engine", "warn", "backend simulado: no hay modelo local conectado"))
        elif engine.ping():
            checks.append(_check("ai_engine", "ok", f"{engine.backend} responde en {engine.endpoint}"))
        else:
            checks.append(_check("ai_engine", "warn", f"{engine.backend} no responde en {engine.endpoint}"))

    found = [b for b, present in BrowserConnector.detect_installed().items() if present]
    checks.append(_check("browsers", "ok" if found else "warn",
                         f"en PATH: {', '.join(found)}" if found else "Firefox/LibreWolf no encontrados en PATH"))

    statuses = {c["status"] for c in checks}
    overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "ok"
    return {"overall": overall, "checks": checks, "capabilities": basic_health()}
