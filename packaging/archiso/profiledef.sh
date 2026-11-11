# Perfil archiso de NEXORA OS (formato actual de archiso >= v60).
# Referencia: /usr/share/archiso/configs/releng/profiledef.sh
output="out"
iso_name="nexora-os"
iso_label="NEXORA_OS_BETA_0_3"
iso_publisher="NEXORA OS Project <https://github.com/octcenano/NexoraOS>"
iso_application="NEXORA OS Beta Live"
iso_version="0.3.0"
install_dir="nexora"
bootmodes=('bios.syslinux' 'uefi.systemd')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86' '-b' '1M' '-Xdict-size' '1M')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/install-nexora.sh"]="0:0:755"
)

[build]
options=()
