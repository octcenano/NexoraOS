# NexoraOS Tools

Herramientas del sistema NexoraOS, distribucion Linux propia basada en Arch.

## Componentes

| Funcion | Componente | Ruta |
|---|---|---|
| F1 Blueprint declarativo | nexora-blueprint | blueprint/ |
| F2 Core A/B atomico | nexora-core | core/ |
| F3 Maquina del tiempo por app | nexora-app | app-time/ |
| F4 Sentinel (seguridad) | nexora-sentinel + antivirus | sentinel/ |
| F4.1 Antivirus | nexora-antivirus | sentinel/antivirus/ |
| F5 Cell (sandbox) | nexora-cell | cell/ |
| F6 NetWall | nexora-netwall | netwall/ |
| F7 Guardian (LLM local) | nexora-guardian | guardian/ |
| F8 Lens (busqueda semantica) | nexora-lens | lens/ |
| F9 Vault (TPM2) | nexora-vault | vault/ |
| F10 Persona (identidad) | nexora-persona | persona/ |
| F11 Privacy | nexora-privacy | privacy/ |
| F12 Doctor | nexora-doctor | doctor/ |
| F13 Recovery | build-recovery-image.sh | recovery/ |
| F14 Perf | nexora-perf | perf/ |
| F15 Bridge | nexora-bridge | bridge/ |
| eBPF transversal | sondas + cargador | ebpf/ |
| Kernel | linux-nexora | kernel/ |
| Tuning por hardware | nexora-hwprofile | tuning/ |
| RAM < 500 MB | nexora-ramopt | ramopt/ |
| Sigilo Tor | nexora-tor + nexora-stealth | tor/ |

## Optimizacion de RAM (< 500 MB)

`nexora-ramopt apply` configura zram (zstd), sysctl de memoria agresivo, set
minimo de servicios y limites systemd (MemoryHigh/MemoryMax, CPUQuota) para los
daemons nexora. `nexora-ramopt status` reporta el consumo actual. Consulte
ramopt/perfiles-escritorio.md para el presupuesto por componente.

## Modo sigilo (Tor)

`nexora-stealth on [nivel]` con niveles: lite (SOCKS), balanced (proxy
transparente con DNS por Tor), advanced (kill-switch nftables: solo el usuario
tor puede salir) e isolated (advanced + microfono y camara bloqueados).
`nexora-tor run <comando>` ejecuta un comando a traves de Tor.

## Instalacion

    make install
    sudo nexora-ramopt apply
    sudo nexora-stealth on balanced

## CI e ISO funcional (GitHub Actions)

El flujo .github/workflows/ci.yml ejecuta en cada push y pull request: validacion
del JSON de firmas, compilacion de los modulos Python (compileall), pruebas de
humo de los CLI bash y Python, y a continuacion construye una ISO funcional con
archiso en un contenedor archlinux:base-devel. El artefacto nexoraos-iso queda
disponible en la pagina del workflow.

Construccion local: instale archiso y ejecute ./archiso/build.sh; el script
ensambla el perfil a partir del releng de Arch, incorpora los paquetes de
archiso/packages.nexora, copia las herramientas dentro del airootfs y genera la
ISO en out/. La ISO incluye el instalador guiado nexora-installer.sh (particionado
automatico, ranuras A/B en btrfs, GRUB, region y teclado en espanol).

## Estado y pendientes

Vea docs/BACKLOG.md para el inventario completo de funcionalidades pendientes y
los criterios de calidad obligatorios (tests, watchdogs, daemons, seguridad).

## Correccion del CI ISO (0.3.1)

build.sh se ejecuta con bash porque push_files no conserva el bit de ejecucion (100644); el contenedor instala git antes del checkout y refresca archlinux-keyring antes de sincronizar.

## CI ISO 0.3.2

El paso de ISO queda separado en dos fases (ensamblado y mkarchiso) para localizar fallos con precision.

CI ISO 0.3.3: reejecucion con workflow corregido (bash archiso/build.sh, pasos separados).

CI 0.3.4: directorio de estado de Core y Privacy con respaldo en ~/.local/state/nexora (los runners no escriben en /var/lib).

CI 0.3.5: Stealth con respaldo de estado en ~/.local/state/nexora y pruebas de humo etiquetadas por comando.

CI 0.3.5: nexora-stealth con respaldo de estado en ~/.local/state/nexora/stealth.
