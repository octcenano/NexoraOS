"""Nexora Kernel Engine (NKE).

Capa transversal de optimización y adaptación sobre las interfaces del
kernel Linux. No modifica el kernel, no carga módulos por decisión propia
y no aplica cambios irreversibles.

Principios:
  - Solo espacio de usuario: /proc, /sys, PSI, cgroups v2, systemd.
  - Las capacidades reales se detectan antes de usar cualquier interfaz.
  - Tres categorías de acción: automática (A), supervisada (B), protegida (C).
  - Todo cambio reversible lleva registro de rollback en el historial.
  - Huella mínima: sondeo adaptativo (aumenta el intervalo en reposo).
"""

from nexora.nke.capabilities import detect_capabilities
from nexora.nke.engine import NKEngine

__all__ = ["detect_capabilities", "NKEngine"]
__version__ = "0.1.0-alpha"
