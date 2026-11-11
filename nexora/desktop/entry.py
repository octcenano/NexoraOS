"""Punto de entrada del comando nexora-desktop (ventana principal)."""

from __future__ import annotations

import sys


def main() -> int:
    from nexora.core.ai_engine import engine_from_config
    from nexora.core.config import ConfigError, load_config
    from nexora.desktop import DesktopUnavailableError, NexoraDesktopApp

    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2
    try:
        app = NexoraDesktopApp(engine=engine_from_config(cfg))
        app.start()
    except PermissionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    try:
        return app.run_gtk()
    except DesktopUnavailableError as exc:
        print(f"Nexora Desktop no disponible: {exc}", file=sys.stderr)
        return 4
    finally:
        if app.running:
            app.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
