# Empaquetado y construcción (base Arch)

## Paquete pacman (CLI de NEXORA)

`PKGBUILD` instala la CLI y la configuración por defecto en el sistema:

```bash
cd packaging/arch
makepkg -si
```

La CLI busca `defaults.json` en este orden: `NEXORA_CONFIG_DIR`, `./config`
(raíz del proyecto), la copia incluida en el paquete Python y
`/usr/share/nexora/config`.

## ISO live (archiso)

`packaging/archiso/` es un perfil mínimo de archiso con la CLI preinstalada.
Es el punto de partida de la Beta 0.3; aún no incluye gestor gráfico ni
servicios systemd de NEXORA.

```bash
sudo pacman -S archiso
./scripts/build-iso.sh
```

## Qué falta para "OS completo" (Beta 0.3+)

- Sandbox de procesos por agente (hoy el aislamiento es lógico).
- Servicios systemd (watchdogs) y sesión gráfica.
- OAuth real en Account Hub.
- Pruebas en hardware real de la ISO.
