# Integración de Nexora Desktop con XFCE

Contenido:

- `nexora-session.sh`: sesión con recuperación. Tres fallos en 60 segundos
  devuelven el escritorio XFCE estándar (sin capa Nexora) y limpian procesos.
  Instalar en `/usr/bin/nexora-session` y seleccionarlo en el gestor de sesión
  o en `.xinitrc` (`exec nexora-session`).
- `autostart/nexora-desktop.desktop`: arranque automático de la ventana
  principal dentro de la sesión (copiar en `/etc/xdg/autostart/`).
- `panel-layout.sh` y `apply-appearance.sh`: aplican con xfconf-query el
  panel y la apariencia (tema Nexora-Dark). Requieren sesión activa.
- `themes/Nexora-Dark/`: tema GTK3 oscuro ( instalar en
  `/usr/share/themes/Nexora-Dark/`).

Principios: XFCE es la base (xfwm4, Thunar, xfce4-settings, xfce4-notifyd);
Nexora Desktop la configura y añade sus paneles. Ningún daemon propio por
panel: la ventana principal es un proceso de usuario con cierre limpio.
