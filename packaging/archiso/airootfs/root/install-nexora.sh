#!/bin/bash
# Instala la CLI de NEXORA OS en el live si el wheel está presente.
# El script de compilación copia dist/*.whl a airootfs/root/ antes de mkarchiso.
set -euo pipefail

if compgen -G "/root/nexora_os-*.whl" >/dev/null; then
  python -m pip install --no-index --find-links=/root nexora-os && rm -f /root/nexora_os-*.whl
else
  echo "[nexora] wheel no incluido en la ISO; CLI no instalada" >&2
fi
