#!/usr/bin/env bash
# archiso/build.sh: ensambla el perfil archiso de NexoraOS a partir del releng
# de Arch, incorpora los paquetes, las herramientas del sistema y construye la ISO.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROFILE="$ROOT/archiso/nexoraos"
REL=/usr/share/archiso/configs/releng

[[ -d $REL ]] || { echo "se requiere archiso instalado (perfil releng en $REL)"; exit 1; }
rm -rf "$PROFILE" work out
mkdir -p "$ROOT/work" "$ROOT/out"
cp -a "$REL" "$PROFILE"

cat "$ROOT/archiso/packages.nexora" >> "$PROFILE/packages.x86_64"
sort -u -o "$PROFILE/packages.x86_64" "$PROFILE/packages.x86_64"

mkdir -p "$PROFILE/airootfs/usr/lib/nexora" "$PROFILE/airootfs/usr/local/bin"
rsync -a --exclude '.git' --exclude 'archiso' --exclude '.github' \
      --exclude 'work' --exclude 'out' "$ROOT/" "$PROFILE/airootfs/usr/lib/nexora/tools/"
rsync -a "$ROOT/archiso/airootfs/" "$PROFILE/airootfs/"
chmod +x "$PROFILE/airootfs/usr/local/bin/nexora-installer.sh"

for b in "$PROFILE"/airootfs/usr/lib/nexora/tools/*/nexora-*; do
  name=$(basename "$b")
  ln -sf "$b" "$PROFILE/airootfs/usr/local/bin/$name"
done

if command -v mkarchiso >/dev/null 2>&1; then
  mkarchiso -v -w "$ROOT/work" -o "$ROOT/out" "$PROFILE"
else
  echo "perfil ensamblado en $PROFILE (mkarchiso no disponible; ejecute: mkarchiso -v -w work -o out $PROFILE)"
fi
