#!/usr/bin/env bash
# build-recovery-image.sh: imagen de recuperacion NexoraOS (squashfs + entrada GRUB).
set -euo pipefail
OUT=${1:-/var/lib/nexora/recovery}
mkdir -p "$OUT"
echo "[recovery] generando imagen squashfs del sistema actual"
mksquashfs / "$OUT/nexora-recovery.sfs" -compress zstd -e /proc /sys /dev /run /tmp /var/lib/nexora/recovery
cat > "$OUT/40_nexora_recovery" <<'GRUB'
#!/bin/sh
cat << 'MENU'
menuentry 'NexoraOS Recovery' {
  linux /boot/vmlinuz-nexora root=LABEL=NEXORA_RECOVERY ro
  initrd /boot/initramfs-nexora.img
}
MENU
GRUB
chmod +x "$OUT/40_nexora_recovery"
echo "[recovery] imagen lista en $OUT/nexora-recovery.sfs"
