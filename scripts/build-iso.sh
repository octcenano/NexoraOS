#!/usr/bin/env bash
# Compila la CLI de NEXORA OS (wheel), ejecuta los tests y, si hay archiso,
# genera la ISO live. Incluye comprobaciones previas y verificación posterior.
# Uso: ./scripts/build-iso.sh [--skip-tests]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/packaging/archiso"
OUT="$ROOT/out"
SKIP_TESTS=false
if [[ "${1:-}" == "--skip-tests" ]]; then
  SKIP_TESTS=true
fi

fail() { echo "[build-iso] ERROR: $*" >&2; exit 1; }
info() { echo "[build-iso] $*"; }

# --- comprobaciones previas -------------------------------------------------
command -v python >/dev/null 2>&1 || fail "python no está en el PATH (instala python)."
python -m build --version >/dev/null 2>&1 || fail "falta 'python -m build' (pacman -S python-build)."
[[ -f "$PROFILE/profiledef.sh" ]] || fail "perfil archiso incompleto: falta profiledef.sh en $PROFILE."
[[ -f "$PROFILE/packages.x86_64" ]] || fail "perfil archiso incompleto: falta packages.x86_64."
[[ -f "$PROFILE/pacman.conf" ]] || fail "perfil archiso incompleto: falta pacman.conf."

cd "$ROOT"

# --- artefactos antiguos ----------------------------------------------------
# Evita reutilizar ISOs y wheels antiguos: se eliminan antes de compilar.
mkdir -p "$OUT"
OLD_ISOS="$(find "$OUT" -maxdepth 1 -name '*.iso' 2>/dev/null || true)"
if [[ -n "$OLD_ISOS" ]]; then
  info "Eliminando ISO(s) antigua(s) en out/ para que el artefacto validado sea solo el nuevo:"
  rm -fv "$OUT"/*.iso "$OUT"/*.sha256
fi
rm -fv "$PROFILE/airootfs/root/"nexora_os-*.whl 2>/dev/null || true

# --- build y tests ----------------------------------------------------------
info "Compilando wheel de nexora-os..."
python -m build --wheel --no-isolation
WHEELS="$(ls dist/*.whl 2>/dev/null || true)"
[[ -n "$WHEELS" ]] || fail "no se generó ningún wheel en dist/."
# Solo el wheel recién generado debe ir a la ISO: limpia dist de wheels viejos.
WHEEL_COUNT="$(printf '%s\n' "$WHEELS" | wc -l)"
if [[ "$WHEEL_COUNT" -gt 1 ]]; then
  fail "dist/ contiene varios wheels ($WHEEL_COUNT); elimina los antiguos para no empaquetar artefactos dudosos."
fi
info "Wheel generado: $WHEELS"

if [[ "$SKIP_TESTS" == false ]]; then
  info "Ejecutando tests..."
  python -m unittest discover -s tests
fi

# --- ISO --------------------------------------------------------------------
if ! command -v mkarchiso >/dev/null 2>&1; then
  info "archiso no instalado: se omite la ISO (pacman -S archiso para habilitarla)."
  info "Wheel generado en dist/. Nada más que hacer aquí."
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  fail "mkarchiso requiere root: ejecuta 'sudo ./scripts/build-iso.sh'."
fi

info "Copiando wheel al perfil archiso..."
mkdir -p "$PROFILE/airootfs/root"
cp "$WHEELS" "$PROFILE/airootfs/root/"

info "Generando ISO live (esto descarga paquetes y puede tardar)..."
mkarchiso -v -w "$OUT/work" -o "$OUT" "$PROFILE"

# --- verificación posterior (solo el artefacto recién generado) --------------
ISO="$(find "$OUT" -maxdepth 1 -name '*.iso' | head -n1)"
[[ -n "$ISO" ]] || fail "mkarchiso terminó pero no hay .iso en out/."
ISO_COUNT="$(find "$OUT" -maxdepth 1 -name '*.iso' | wc -l)"
[[ "$ISO_COUNT" -eq 1 ]] || fail "hay $ISO_COUNT ISOs en out/; no está claro cuál es la nueva. Abortando."

info "Verificando la ISO generada: $ISO"
ls -lh "$ISO"
sha256sum "$ISO" | tee "$ISO.sha256"
if command -v file >/dev/null 2>&1; then
  file "$ISO"
  file "$ISO" | grep -q "DOS/MBR boot sector\|ISO 9660" || fail "la ISO no parece una imagen ISO 9660 válida."
fi
if command -v isoinfo >/dev/null 2>&1; then
  isoinfo -d -i "$ISO" | grep -E "Volume id|El Torito" || fail "la ISO no tiene estructura El Torito (arranque)."
else
  info "isoinfo no disponible: no se puede verificar El Torito aquí."
fi
info "Verificación de arranque real (QEMU/hardware): NO ejecutada automáticamente; hazla antes de distribuir."
info "ISO lista en $ISO (checksum en $ISO.sha256)"
