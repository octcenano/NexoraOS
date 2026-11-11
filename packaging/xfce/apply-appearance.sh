#!/bin/bash
# Aplica la identidad visual de Nexora Desktop en una sesión XFCE activa:
# tema oscuro Nexora-Dark, iconos estándar, tipografía legible.
# Requiere xfconf-query y el tema instalado (packaging/xfce/themes).

set -eu

if ! command -v xfconf-query > /dev/null 2>&1; then
  echo "Error: xfconf-query no está instalado (paquete xfconf)" >&2
  exit 1
fi

apply() {
  local channel="$1" prop="$2" type="$3" value="$4"
  if xfconf-query -c "$channel" -p "$prop" > /dev/null 2>&1; then
    xfconf-query -c "$channel" -p "$prop" -s "$value"
  else
    xfconf-query -c "$channel" -p "$prop" -n -t "$type" -s "$value"
  fi
}

apply xsettings /Net/ThemeName string "Nexora-Dark"
apply xsettings /Net/IconThemeName string "Adwaita"
apply xsettings /Gtk/ApplicationPreferDarkTheme bool true
apply xsettings /Gtk/FontName string "Cantarell 11"
apply xfwm4 /general/theme string "Nexora-Dark"

echo "Apariencia Nexora aplicada (tema oscuro, acento y tipografía)."
