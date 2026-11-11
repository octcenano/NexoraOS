# Empaquetado y construcción (base Arch)

## Paquete pacman (CLI de NEXORA)

`PKGBUILD` instala la CLI, la configuración por defecto del sistema y las unidades systemd opcionales:

```bash
cd packaging/arch
makepkg -si
```

- Fuente: git fijado por tag (`#tag=v$pkgver`); el SHA del commit verifica la fuente (por eso `sha256sums=('SKIP')` es aceptable aquí).
- La CLI busca `defaults.json` en este orden: `NEXORA_CONFIG_DIR`, `./config` (raíz del proyecto), la copia incluida en el paquete Python y `/usr/share/nexora/config`. Una instalación limpia funciona sin variables de entorno.

## Watchdog como servicio (opcional)

```bash
sudo useradd -r -s /usr/bin/nologin nexora
sudo systemctl daemon-reload
sudo systemctl enable --now nexora-watchdog        # unidad del sistema
# o, por usuario: systemctl --user enable --now nexora-watchdog
```

Desinstalación:

```bash
sudo systemctl disable --now nexora-watchdog
sudo rm /usr/lib/systemd/system/nexora-watchdog.service
# unidad de usuario: systemctl --user disable --now nexora-watchdog
```

Estado: las unidades están escritas y endurecidas (Restart acotado, NoNewPrivileges, ProtectSystem=strict) pero **no probadas en un host real**.

## ISO live (archiso)

`packaging/archiso/` es un perfil en formato archiso actual con la CLI preinstalada en el live (el wheel se copia a `airootfs/root/` y `install-nexora.sh` lo instala al arrancar).

```bash
sudo pacman -S archiso
sudo ./scripts/build-iso.sh
```

El script comprueba requisitos, valida el perfil, ejecuta los tests, genera la ISO y la verifica (sha256, `file`, isoinfo). Estado: perfil revisado, **ISO nunca generada** (ver `docs/QA_REPORT.md`).

## Qué falta para "OS completo" (Beta 0.4+)

- Sandbox de procesos por agente (hoy el aislamiento es lógico).
- Servicios systemd adicionales, sesión gráfica e instalador.
- OAuth real en Account Hub.
- Pruebas de la ISO en VM y hardware real.
