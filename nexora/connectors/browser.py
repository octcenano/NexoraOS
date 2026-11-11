"""Contrato de integraciÃ³n con navegadores (Firefox y LibreWolf).

Este mÃ³dulo NUNCA lee contraseÃ±as, cookies ni tokens de los perfiles del
navegador. Solo declara quÃ© navegadores se soportan y detecta si hay un
ejecutable en el PATH.
"""

from __future__ import annotations

import shutil
from typing import Optional

SUPPORTED_BROWSERS = ("firefox", "librewolf")


class BrowserConnector:
    """Contrato seguro. ``browser=None`` significa ambos navegadores (``both``)."""

    def __init__(self, browser: Optional[str] = None):
        if browser is not None and browser not in SUPPORTED_BROWSERS:
            raise ValueError(f"Navegador no soportado: {browser}")
        self.browser = browser

    @property
    def supported_browsers(self) -> tuple:
        return SUPPORTED_BROWSERS

    @property
    def selected(self) -> tuple:
        return SUPPORTED_BROWSERS if self.browser is None else (self.browser,)

    @staticmethod
    def detect_installed() -> dict:
        """Busca los ejecutables en el PATH. No abre ni inspecciona perfiles."""
        return {b: shutil.which(b) is not None for b in SUPPORTED_BROWSERS}

    def status(self) -> dict:
        return {
            "browser": self.browser or "both",
            "integration": "not_configured",
            "auth": "official OAuth/API or explicit local authorization required",
            "secret_extraction": False,
        }
