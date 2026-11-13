"""NGNE: Gaming Network Engine.

Diagnóstico de red de solo lectura, optimizador de colas (fq-codel/CAKE)
con restauración exacta, DNS solo con consentimiento explícito y perfiles
de juego adaptados al hardware y al tipo de enlace. Módulos:
  - diagnostics.py: diagnóstico sin efectos (interfaces, latencia, DNS).
  - profiles.py: los seis perfiles de juego y su adaptación.
  - optimizer.py: colas fq-codel/CAKE y DNS con verificación y restauración.
  - engine.py: integración de diagnóstico, perfiles y optimizador.
"""

from nexora.gaming.network.diagnostics import NetworkDiagnostics

__all__ = ["NetworkDiagnostics"]
