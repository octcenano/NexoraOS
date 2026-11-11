# Guía de instalación — NexoraOS

## Desde el paquete (Arch Linux)

Requiere el tag `v0.4.0` publicado (no creado todavía; ver QA_REPORT).

```bash
git clone https://github.com/octcenano/NexoraOS
cd NexoraOS/packaging/arch
makepkg -si
```

El paquete instala la CLI (`nexora`, `nexora-watchdog`), la configuración por defecto en `/usr/share/nexora/config/` y las unidades systemd opcionales del watchdog.

## Desde el código

```bash
git clone https://github.com/octcenano/NexoraOS && cd NexoraOS
python -m pip install .
nexora --help
```

## Primer arranque

```bash
nexora health              # diagnóstico del core
nexora-watchdog --diagnose # informe del watchdog sin efectos
```

Si `nexora health` no encuentra configuración, comprueba que `config/defaults.json` está en el repositorio (desarrollo) o en `/usr/share/nexora/config/` (paquete). La configuración de usuario va en `~/.config/nexora/user.json` (plantilla: `config/user.example.json`).

## Watchdog (opcional)

```bash
# Sesión de usuario (recomendado)
systemctl --user enable --now nexora-watchdog
systemctl --user status nexora-watchdog

# Sistema (requiere usuario 'nexora' sin privilegios)
sudo useradd -r -s /usr/bin/nologin nexora
sudo systemctl enable --now nexora-watchdog
```

## Desinstalación

```bash
sudo pacman -R nexora-os
systemctl --user disable --now nexora-watchdog 2>/dev/null || true
rm -rf ~/.config/nexora
```

## ISO live (pendiente de verificación)

```bash
sudo ./scripts/build-iso.sh
```

El script compila el wheel, ejecuta los tests y, si archiso está instalado, genera y verifica la ISO. Aviso: la ISO no se ha construido nunca de extremo a extremo (ver `docs/QA_REPORT.md`).
