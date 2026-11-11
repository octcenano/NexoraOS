# Perfil archiso mínimo de NEXORA OS (punto de partida de la Beta 0.3).
# Genera una ISO live Arch con la CLI de NEXORA preinstalada.
# Uso: sudo ./scripts/build-iso.sh (requiere archiso instalado).

output="out"
iso_name="nexora-os"
iso_label="NEXORA_OS_BETA"
iso_publisher="NEXORA OS Project"
iso_application="NEXORA OS Beta Live"
install_dir="nexora"
bootmodes=('bios.syslinux' 'uefi.systemd')

[initcpio]
hooks_base="base udev"
hooks_live="archiso archiso_loop_mnt"

[efi]
efi_arch="x86-64"
