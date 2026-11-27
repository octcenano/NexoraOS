#!/usr/bin/env bash
# nexora-installer.sh: instalador guiado de NexoraOS (A/B en btrfs).
set -euo pipefail
echo "NexoraOS - instalador guiado (modo A/B sobre btrfs)"
read -rp "Disco de destino (ejemplo: /dev/vda): " DISK
[[ -b "$DISK" ]] || { echo "disco invalido: $DISK"; exit 1; }
echo "ATENCION: se borraran todos los datos de $DISK"
read -rp "Escriba SI para continuar: " CONF
[[ "$CONF" == "SI" ]] || { echo "cancelado"; exit 1; }

wipefs -a "$DISK"
echo -e "label: gpt\nsize=512M, type=uefi\nsize=0, type=linux" | sfdisk "$DISK"
PART_EFI="${DISK}1"; PART_ROOT="${DISK}2"
[[ $DISK == /dev/nvme* ]] && { PART_EFI="${DISK}p1"; PART_ROOT="${DISK}p2"; }

mkfs.fat -F32 "$PART_EFI"
mkfs.btrfs -f -L NEXORA "$PART_ROOT"
mount "$PART_ROOT" /mnt
btrfs subvolume create /mnt/@root-a
btrfs subvolume create /mnt/@root-b
btrfs subvolume create /mnt/@home
umount /mnt
mount -o subvol=@root-a,compress=zstd "$PART_ROOT" /mnt
mkdir -p /mnt/{boot,home}
mount -o subvol=@home,compress=zstd "$PART_ROOT" /mnt/home
mount "$PART_EFI" /mnt/boot

pacstrap /mnt base linux linux-firmware grub efibootmgr networkmanager \
             btrfs-progs jq python nftables tor torsocks zram-generator age bubblewrap
genfstab -U /mnt >> /mnt/etc/fstab

# Herramientas NexoraOS dentro del sistema instalado
cp -a /usr/lib/nexora/tools /mnt/usr/lib/nexora
mkdir -p /mnt/usr/local/bin
for b in /mnt/usr/lib/nexora/tools/*/nexora-* /mnt/usr/lib/nexora/tools/tor/nexora-*; do
  name=$(basename "$b")
  ln -sf "$b" "/mnt/usr/local/bin/$name"
done
cp -a /mnt/usr/lib/nexora/tools/ramopt/units/*.service /mnt/etc/systemd/system/
cp -a /mnt/usr/lib/nexora/tools/tor/units/*.service /mnt/etc/systemd/system/
cp -a /mnt/usr/lib/nexora/tools/sentinel/units/*.service /mnt/etc/systemd/system/

arch-chroot /mnt bash -e <<CHROOT
echo "es_ES.UTF-8 UTF-8" > /etc/locale.gen
locale-gen
echo "LANG=es_ES.UTF-8" > /etc/locale.conf
echo "KEYMAP=es" > /etc/vconsole.conf
ln -sf /usr/share/zoneinfo/Europe/Madrid /etc/localtime
systemctl enable NetworkManager systemd-zram-setup@zram0.service
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=NexoraOS
grub-mkconfig -o /boot/grub/grub.cfg
echo "root:nexora" | chpasswd
CHROOT

echo "Instalacion completada. Reinicie y entre como root (clave temporal: nexora)."
