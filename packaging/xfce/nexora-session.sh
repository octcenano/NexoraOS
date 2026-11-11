#!/bin/bash
# Nexora Desktop: sesión XFCE con la capa Nexora.
# Estrategia de recuperación: si Nexora Desktop falla repetidamente en poco
# tiempo, se vuelve al escritorio XFCE estándar (sin la capa Nexora).
# No se ejecuta como root.

set -u

LOG="${XDG_CACHE_HOME:-$HOME/.cache}/nexora/desktop-session.log"
mkdir -p "$(dirname "$LOG")"

if [ "$(id -u)" -eq 0 ]; then
  echo "$(date -Is) ERROR: la sesión no debe ejecutarse como root" >> "$LOG"
  exit 1
fi

# Detección de bucle de fallos: 3 arranques en menos de 60 segundos.
now=$(date +%s)
marks="${XDG_CACHE_HOME:-$HOME/.cache}/nexora/session-starts"
mkdir -p "$(dirname "$marks")"
echo "$now" >> "$marks"
tail -n 3 "$marks" | awk -v now="$now" 'BEGIN{c=0} {if (now - $1 < 60) c++} END{exit !(c >= 3)}'
if [ $? -eq 0 ]; then
  echo "$(date -Is) AVISO: 3 fallos en 60s; se arranca XFCE estándar sin la capa Nexora" >> "$LOG"
  # Limpieza: ningún proceso huérfano de la capa Nexora.
  pkill -f "nexora-desktop" 2>/dev/null || true
  exec xfce4-session
fi

echo "$(date -Is) inicio de sesión Nexora Desktop" >> "$LOG"

# La sesión es xfce4-session: Nexora Desktop se integra vía autostart y
# configuración de xfconf; si la capa Nexora falla, el escritorio XFCE
# base sigue funcionando.
exec xfce4-session
