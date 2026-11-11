#!/usr/bin/env bash
# Compila la CLI de NEXORA OS (wheel) y, si hay archiso, la ISO live beta.
# Uso: ./scripts/build-iso.sh [raiz-del-proyecto]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/3] Compilando wheel de nexora-os..."
python -m build --wheel --no-isolation

echo "[2/3] Ejecutando tests..."
python -m unittest discover -s tests

if command -v mkarchiso >/dev/null 2>&1; then
  echo "[3/3] Generando ISO live (archiso)..."
  mkdir -p out
  mkarchiso -v -w out/work -o out packaging/archiso
  echo "ISO generada en out/"
else
  echo "[3/3] archiso no instalado: se omite la ISO (pacman -S archiso para habilitarla)."
fi
