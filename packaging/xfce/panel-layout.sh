#!/bin/bash
# Aplica el diseño del panel de Nexora Desktop con xfconf-query.
# Requiere una sesión XFCE activa (xfconfd en ejecución).
# Sin sesiones activas el script falla con un mensaje claro: no simula nada.

set -eu

if ! command -v xfconf-query > /dev/null 2>&1; then
  echo "Error: xfconf-query no está instalado (paquete xfconf)" >&2
  exit 1
fi

CHANNEL=xfce4-panel
PROP_BASE=/panels/panel-1

set_prop() {
  local prop="$1"; shift
  if xfconf-query -c "$CHANNEL" -p "$prop" > /dev/null 2>&1; then
    xfconf-query -c "$CHANNEL" -p "$prop" "$@"
  else
    xfconf-query -c "$CHANNEL" -p "$prop" -n -t "$1" "$@"
  fi
}

# Nota: el diseño fino de plugins (plugin-ids, plugin-N) se gestiona mejor
# desde xfce4-panel en modo "modo de edición". Este script fija lo básico:
set_prop "$PROP_BASE/position" -t string -s "p=6;x=0;y=0"
set_prop "$PROP_BASE/size" -t uint -s 34
set_prop "$PROP_BASE/length-adjust" -t bool -s true
set_prop "$PROP_BASE/autohide-behavior" -t uint -s 0

echo "Configuración básica del panel aplicada. Los plugins concretos"
echo "(whiskermenu, launcher de Nexora, systray, reloj) se editan con"
echo "xfce4-panel en modo de edición o con un perfil xfconf completo."
