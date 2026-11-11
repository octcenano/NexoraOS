#!/usr/bin/env bash
# Compila la CLI de NEXORA OS (wheel), ejecuta los tests y, si hay archiso,
# genera la ISO live. Incluye comprobaciones previas y verificación posterior.
# Uso: ./scripts/build-iso.sh [--skip-tests]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/packaging/archiso"
SKIP_TESTS=false
[[ "${1:-}" == "--skip-tests" ]] && SKIP_TESTS=true

fail() { echo "[build-iso] ERROR: $*" >&2; exit 1; }
info() { echo "[build-iso] $*"; }

# --- comprobaciones previas -------------------------------------------------
command -v python >/dev/null 2>&1 || fail "python no está en el PATH (instala python)."
python -m build --version >/dev/null 2>&1 || fail "falta 'python -m build' (pacman -S python-build)."
[[ -f "$PROFILE/profiledef.sh" ]] || fail "perfil archiso incompleto: falta profiledef.sh en $PROFILE."
[[ -f "$PROFILE/packages.x86_64" ]] || fail "perfil archiso incompleto: falta packages.x86_64."
[[ -f "$PROFILE/pacman.conf" ]] || fail "perfil archiso incompleto: falta pacman.conf."

cd "$ROOT"

# --- build y tests ----------------------------------------------------------
info "Compilando wheel de nexora-os..."
python -m build --wheel --no-isolation
ls dist/*.whl >/dev/null 2>&1 || fail "no se generó ningún wheel en dist/."

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
mkdir -p "$PROFILE/airootfs/root" out
cp dist/*.whl "$PROFILE/airootfs/root/"

info "Generando ISO live (esto descarga paquetes y puede tardar)..."
mkarchiso -v -w "$ROOT/out/work" -o "$ROOT/out" "$PROFILE"

ISO="$(ls "$ROOT"/out/*.iso 2>/dev/null | head -n1 || true)"
[[ -n "$ISO" ]] || fail "mkarchiso terminó pero no hay .iso en out/."

# --- verificación posterior -------------------------------------------------
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
info "ISO lista en $ISO"
