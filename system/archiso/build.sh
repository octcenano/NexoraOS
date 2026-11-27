#!/usr/bin/env bash
# archiso/build.sh: ensambla el perfil archiso de NexoraOS a partir del releng
# de Arch y construye la ISO.
# Uso: build.sh [all|assemble|iso]   (por defecto: all)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROFILE="$ROOT/archiso/nexoraos"
REL=/usr/share/archiso/configs/releng
MODE=${1:-all}
case "$MODE" in
  all|assemble|iso) ;;
  *) echo "uso: $0 [all|assemble|iso]"; exit 2;;
esac

if [[ $MODE == all || $MODE == assemble ]]; then
  [[ -d $REL ]] || { echo "se requiere archiso instalado (perfil releng en $REL)"; exit 1; }
  echo "[1/4] preparando directorios"
  rm -rf "$PROFILE" "$ROOT/work" "$ROOT/out"
  mkdir -p "$ROOT/work" "$ROOT/out"
  echo "[2/4] copiando perfil releng de archiso"
  cp -a "$REL" "$PROFILE"

  echo "[3/4] paquetes y herramientas"
  cat "$ROOT/archiso/packages.nexora" >> "$PROFILE/packages.x86_64"
  sort -u -o "$PROFILE/packages.x86_64" "$PROFILE/packages.x86_64"
  mkdir -p "$PROFILE/airootfs/usr/lib/nexora" "$PROFILE/airootfs/usr/local/bin"
  rsync -a --exclude '.git' --exclude 'archiso' --exclude '.github' \
        --exclude 'work' --exclude 'out' "$ROOT/" "$PROFILE/airootfs/usr/lib/nexora/tools/"
  rsync -a "$ROOT/archiso/airootfs/" "$PROFILE/airootfs/"
  chmod +x "$PROFILE/airootfs/usr/local/bin/nexora-installer.sh"
  for b in "$PROFILE"/airootfs/usr/lib/nexora/tools/*/nexora-*; do
    [[ -e $b ]] || continue
    name=$(basename "$b")
    ln -sf "$b" "$PROFILE/airootfs/usr/local/bin/$name"
  done
  echo "perfil ensamblado en $PROFILE"
fi

if [[ $MODE == all || $MODE == iso ]]; then
  command -v mkarchiso >/dev/null 2>&1 || { echo "mkarchiso no disponible"; exit 1; }
  echo "[4/4] generando ISO con mkarchiso"
  mkarchiso -v -w "$ROOT/work" -o "$ROOT/out" "$PROFILE"
  ls -lh "$ROOT/out"
fi
