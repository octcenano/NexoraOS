"""Carga y validaciÃ³n de configuraciÃ³n.

La configuraciÃ³n NO es un sitio para secretos: cualquier clave que parezca una
credencial se rechaza (decisiÃ³n de diseÃ±o 5). Los secretos viven en el vault.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from nexora import __version__
from nexora.connectors.browser import SUPPORTED_BROWSERS
from nexora.core.ai_engine import BACKENDS
from nexora.core.registry import MODES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"

SECRET_KEY_FRAGMENTS = ("password", "passwd", "secret", "token", "api_key", "apikey", "cookie", "credential", "private_key")
_URL_WITH_CREDENTIALS = re.compile(r"://[^/\s@]+:[^/\s@]*@")

METEOROLOGY_PROVIDERS = ("simulated", "open-meteo")
VAULT_BACKENDS = ("memory", "keyring")


class ConfigError(ValueError):
    pass


def find_secret_like(obj: Any, path: str = "") -> list:
    """Devuelve las rutas de claves/valores que parecen credenciales."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else str(key)
            if any(frag in str(key).lower() for frag in SECRET_KEY_FRAGMENTS):
                found.append(here)
            found.extend(find_secret_like(value, here))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            found.extend(find_secret_like(value, f"{path}[{i}]"))
    elif isinstance(obj, str) and _URL_WITH_CREDENTIALS.search(obj):
        found.append(f"{path} (URL con credenciales)")
    return found


def deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"No se pudo leer {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} debe contener un objeto JSON")
    return data


def default_user_config_path() -> Path:
    env = os.environ.get("NEXORA_USER_CONFIG")
    if env:
        return Path(env)
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "nexora" / "user.json"


def validate_config(cfg: dict) -> None:
    secrets = find_secret_like(cfg)
    if secrets:
        raise ConfigError(f"La configuraciÃ³n no puede contener secretos: {', '.join(secrets)}")
    if cfg.get("agent_memory_policy") != "isolated_per_mode":
        raise ConfigError("agent_memory_policy debe ser 'isolated_per_mode' (decisiÃ³n fija)")
    for browser in cfg.get("browsers", []):
        if browser not in SUPPORTED_BROWSERS:
            raise ConfigError(f"Navegador no soportado en 'browsers': {browser}")
    preferred = cfg.get("preferred_browser")
    if preferred is not None and preferred not in SUPPORTED_BROWSERS:
        raise ConfigError(f"preferred_browser no soportado: {preferred}")
    unknown = [m for m in cfg.get("modes_enabled", []) if m not in MODES]
    if unknown:
        raise ConfigError(f"Modos desconocidos en modes_enabled: {unknown}")
    if cfg.get("ai_engine", {}).get("backend") not in BACKENDS:
        raise ConfigError(f"ai_engine.backend debe ser uno de {sorted(BACKENDS)}")
    if cfg.get("meteorology", {}).get("provider") not in METEOROLOGY_PROVIDERS:
        raise ConfigError(f"meteorology.provider debe ser uno de {METEOROLOGY_PROVIDERS}")
    if cfg.get("vault", {}).get("backend") not in VAULT_BACKENDS:
        raise ConfigError(f"vault.backend debe ser uno de {VAULT_BACKENDS}")
    if not isinstance(cfg.get("telemetry", {}).get("enabled"), bool):
        raise ConfigError("telemetry.enabled debe ser booleano")


def _default_config_candidates() -> list:
    """Rutas donde buscar defaults.json, en orden de prioridad."""
    candidates = [DEFAULT_CONFIG_DIR, Path(__file__).resolve().parents[1] / "config",
                  Path("/usr/share/nexora/config")]
    env = os.environ.get("NEXORA_CONFIG_DIR")
    if env:
        candidates.insert(0, Path(env))
    return candidates


def find_defaults_file(config_dir) -> Path:
    if config_dir:
        path = Path(config_dir) / "defaults.json"
        if not path.is_file():
            raise ConfigError(f"No se encuentra {path} (usa NEXORA_CONFIG_DIR)")
        return path
    for cdir in _default_config_candidates():
        path = cdir / "defaults.json"
        if path.is_file():
            return path
    raise ConfigError("No se encuentra defaults.json. Define NEXORA_CONFIG_DIR o reinstala el paquete.")


def load_config(config_dir: Optional[Path] = None, user_path: Optional[Path] = None) -> dict:
    """Carga defaults.json y, si existe, la configuraciÃ³n de usuario encima."""
    try:
        cfg = _read_json(find_defaults_file(config_dir))
    except FileNotFoundError:
        raise ConfigError("No se encuentra defaults.json (usa NEXORA_CONFIG_DIR)") from None

    upath = Path(user_path) if user_path else default_user_config_path()
    try:
        cfg = deep_merge(cfg, _read_json(upath))
    except FileNotFoundError:
        pass

    validate_config(cfg)
    if cfg.get("version") != __version__:
        raise ConfigError(f"VersiÃ³n de config ({cfg.get('version')}) distinta de la del paquete ({__version__})")
    return cfg
