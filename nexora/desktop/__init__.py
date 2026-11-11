"""Nexora Desktop: capa gráfica propia sobre XFCE.

Arquitectura:
  - Modelos puros (shell, dashboard, mode_center, nke_control, hub,
    system_center, app): sin dependencias gráficas, testables.
  - Vista GTK3 (gtkui) con importación diferida: si PyGObject no está
    disponible, los modelos siguen funcionando y la CLI lo declara.
  - XFCE es la base (panel, gestor de ventanas, ajustes, notificaciones);
    Nexora Desktop no la sustituye: la configura y la extiende.
"""

from nexora.desktop.app import DesktopUnavailableError, NexoraDesktopApp

__all__ = ["DesktopUnavailableError", "NexoraDesktopApp"]
