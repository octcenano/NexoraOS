"""Carga y validación de configuración.

La configuración NO es un sitio para secretos: cualquier clave que parezca una
credencial se rechaza (decisión de diseño 5). Los secretos viven en el vault.

Búsqueda de defaults.json (en orden):
  1. ``config_dir`` explícito (parámetro).
  2. ``NEXORA_CONFIG_DIR`` (entorno).
  3. ``config/`` en la raíz del proyecto (desarrollo).
  4. Copia incluida en el paquete (``nexora/config/``).
  5. ``/usr/share/nexora/config`` (instalación del sistema, PKGBUILD).

Así, una instalación limpia funciona sin variables de entorno.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from nexora import __version__
from nexora.connectors.browser import SUPPORTED_BROWSERS
from nexora.core.ai_engine import BACKENDS
from nexora.core.registry import MODES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"

# Claves conocidas: defaults + ejemplo de usuario. Cualquier otra clave se rechaza.
KNOWN_TOP_LEVEL_KEYS = frozenset({
    "product", "version", "profile_strategy", "browsers", "preferred_browser",
    "agent_memory_policy", "modes_enabled", "ai_engine", "local_model_endpoint",
    "meteorology", "vault", "telemetry", "permissions",
    "display_name", "connected_services", "projects_index_path",
})

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


def _default_config_candidates() -> list:
    candidates = [DEFAULT_CONFIG_DIR, Path(__file__).resolve().parents[1] / "config",
                  Path("/usr/share/nexora/config")]
    env = os.environ.get("NEXORA_CONFIG_DIR")
    if env:
        candidates.insert(0, Path(env))
    return candidates


def find_defaults_file(config_dir: Optional[Path] = None) -> Path:
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


def validate_config(cfg: dict) -> None:
    secrets = find_secret_like(cfg)
    if secrets:
        raise ConfigError(f"La configuración no puede contener secretos: {', '.join(secrets)}")
    unknown = [k for k in cfg if k not in KNOWN_TOP_LEVEL_KEYS]
    if unknown:
        raise ConfigError(f"Claves desconocidas en la configuración: {sorted(unknown)}")
    if not isinstance(cfg.get("browsers", []), list):
        raise ConfigError("browsers debe ser una lista")
    if cfg.get("agent_memory_policy") != "isolated_per_mode":
        raise ConfigError("agent_memory_policy debe ser 'isolated_per_mode' (decisión fija)")
    for browser in cfg.get("browsers", []):
        if browser not in SUPPORTED_BROWSERS:
            raise ConfigError(f"Navegador no soportado en 'browsers': {browser}")
    preferred = cfg.get("preferred_browser")
    if preferred is not None and preferred not in SUPPORTED_BROWSERS:
        raise ConfigError(f"preferred_browser no soportado: {preferred}")
    if not isinstance(cfg.get("modes_enabled", []), list):
        raise ConfigError("modes_enabled debe ser una lista")
    unknown_modes = [m for m in cfg.get("modes_enabled", []) if m not in MODES]
    if unknown_modes:
        raise ConfigError(f"Modos desconocidos en modes_enabled: {unknown_modes}")
    if not isinstance(cfg.get("ai_engine", {}), dict):
        raise ConfigError("ai_engine debe ser un objeto")
    if cfg.get("ai_engine", {}).get("backend") not in BACKENDS:
        raise ConfigError(f"ai_engine.backend debe ser uno de {sorted(BACKENDS)}")
    if not isinstance(cfg.get("meteorology", {}), dict):
        raise ConfigError("meteorology debe ser un objeto")
    if cfg.get("meteorology", {}).get("provider") not in METEOROLOGY_PROVIDERS:
        raise ConfigError(f"meteorology.provider debe ser uno de {METEOROLOGY_PROVIDERS}")
    if not isinstance(cfg.get("vault", {}), dict):
        raise ConfigError("vault debe ser un objeto")
    if cfg.get("vault", {}).get("backend") not in VAULT_BACKENDS:
        raise ConfigError(f"vault.backend debe ser uno de {VAULT_BACKENDS}")
    if not isinstance(cfg.get("telemetry", {}).get("enabled"), bool):
        raise ConfigError("telemetry.enabled debe ser booleano")


def load_config(config_dir: Optional[Path] = None, user_path: Optional[Path] = None) -> dict:
    """Carga defaults.json y, si existe, la configuración de usuario encima."""
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
        raise ConfigError(f"Versión de config ({cfg.get('version')}) distinta de la del paquete ({__version__})")
    return cfg


def write_user_config(cfg: dict, path: Optional[Path] = None) -> Path:
    """Escribe la configuración de usuario de forma segura.

    Valida antes de escribir, crea el directorio con permisos 700 y el archivo
    con 600, y escribe de forma atómica (temporal + rename) para no dejar un
    archivo corrupto si la operación se interrumpe.
    """
    validate_config(dict(cfg))
    if find_secret_like(cfg):
        raise ConfigError("La configuración no puede contener secretos")
    target = Path(path) if path else default_user_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    payload = json.dumps(cfg, ensure_ascii=False, indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".user-", suffix=".json.tmp")
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
