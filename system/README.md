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
| NKE (nucleo adaptativo, P1) | nexora-nke | nke/ |
| Watchdogs (P1) | nexora-watchdog | watchdogs/ |
| Consola Sentinel AV (P1) | nexora-av-console | sentinel/ |
| Supervisor de salud (P1) | nexora-supervisor | watchdogs/ |
| Nexora Session (P1) | nexora-session | session/ |
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
ensambla el perfil a partir del releng de Arch pero SUSTITUYE su lista de
paquetes por la propia y minima de archiso/packages.nexora (17 paquetes: solo
arranque, red, instalacion y herramientas; archinstall y utilidades ajenas
excluidas), copia las herramientas al airootfs y genera la ISO en out/.

Instalador exclusivo: nexora-installer sustituye por completo a archinstall,
que no esta presente en la ISO. Flujo guiado con menus numerados, valores por
defecto, resumen y confirmacion: disco, perfil NexoraOS (game/ai/office/battery/
meteo), nivel de sigilo Tor opcional (lite/balanced/advanced/isolated),
hostname, zona horaria, usuario; esquema fijo GPT + btrfs A/B con @root-b como
instantanea identica desde el primer arranque y GRUB con entrada de respaldo.
Modo no interactivo para QEMU: --auto <disco> --yes [--profile P] [--stealth N].
Al arrancar el live se ofrece ejecutar el instalador automaticamente.

## NKE y watchdogs (P1 Integracion)

nexora-nke es el nucleo adaptativo: unifica Sentinel, Guardian y Core bajo un
bucle de decision (carga, memoria disponible, temperatura, bateria). Aplica
perfiles automaticamente, coordina los cinco modos (game, office, forge,
hacking, stealth) y revierte cualquier cambio que empeore el rendimiento
(recuperacion automatica). nexora-watchdog supervisa los daemons y los
reinicia. Ambos operan con presupuestos de memoria (MemoryMax 64M y 32M).
Comandos: nexora-nke {once|run|status|mode <m>|decide|explain};
nexora-watchdog {once|run|status}.

## Consola Sentinel, Supervisor de salud y Nexora Session (P1)

- nexora-av-console: eventos sospechosos filtrables, auditoria completa de
  acciones, cuarentena con respuestas autorizadas (restaurar exige RESTAURAR y
  purgar exige PURGAR; ambas quedan registradas con usuario y sello de
  autorizacion) e integracion con NetWall: contain <proceso> detiene el
  proceso y le deniega la salida de red.
- nexora-supervisor (Sentinel Supervisor): watchdogs centrales, comprobacion
  de servicios, deteccion de bloqueos obsoletos (db.lck mayor de una hora sin
  pacman vivo, unidades en fallo) y procesos huerfanos, recuperacion
  controlada por etapas (watchdog, doctor --auto, valoracion de rollback),
  diagnostico y mantenimiento (vacuum del journal, timers).
- nexora-session: Aura (temas oscuro/claro/alto-contraste con acento), audio y
  sonidos de eventos, notificaciones y no molestar, integracion con XFCE,
  preferencias de usuario persistidas en JSON y huella audiovisual propia con
  chime de arranque generado por el sistema (WAV 8 kHz generado internamente).

## Estado y pendientes

Vea docs/BACKLOG.md para el inventario completo de funcionalidades pendientes y
los criterios de calidad obligatorios (tests, watchdogs, daemons, seguridad).
