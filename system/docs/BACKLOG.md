# NEXORA OS - Master list de ideas y funcionalidades pendientes

Inventario de ideas pendientes. Reglas: no marcar como completado sin codigo
real verificado; toda implementacion incluye tests, revision de bugs, seguridad,
UX/UI, watchdogs y daemons; compatibilidad con el nucleo adaptativo; sin modulos
aislados.

Estado 0.3.0: RAM < 500 MB (ramopt) y modo sigilo Tor con niveles Lite /
Balanced / Advanced / Isolated implementados. CI en GitHub Actions con
validacion y construccion de ISO funcional (archiso). El resto queda pendiente
y se gestiona por fases (seccion 16).

## 1. Nucleo adaptativo y Nexora Kernel Engine
- [ ] Aplicacion real de politicas de CPU
- [ ] Gestion dinamica de RAM entre aplicaciones y agentes
- [ ] Asignacion inteligente de recursos segun tareas
- [ ] Monitorizacion de GPU y VRAM
- [ ] Monitorizacion de bateria
- [ ] Aplicacion real de cgroups en hardware
- [ ] Programas eBPF propios (parcial: sondas en ebpf/)
- [ ] Coordinacion Core/Engine/Guardian/Adapt
- [ ] Adaptacion automatica por hardware, temperatura y carga
- [ ] Prioridades inteligentes de procesos
- [ ] Recuperacion automatica si una optimizacion empeora el rendimiento
- [ ] Deteccion de cuellos de botella
- [ ] Optimizacion dinamica sin cambio manual de perfil

## 2. Sentinel
- [x] Sentinel AV: antivirus defensivo (nexora-antivirus)
- [x] Analisis automatico de descargas
- [ ] Deteccion con firmas YARA (actualmente regex propias + hashes)
- [x] Analisis de comportamiento sospechoso (nexora-sentinel + eBPF)
- [ ] Deteccion de persistencia de malware
- [x] Deteccion de escaladas de privilegios
- [ ] Monitorizacion de procesos en tiempo real continua
- [x] Integracion con eBPF
- [x] Cuarentena
- [x] Historial de amenazas (events.jsonl)
- [ ] Watchdogs especializados
- [ ] Integracion con Guardian
- [ ] Recuperacion automatica ante incidentes
- [ ] Proteccion en tiempo real configurable
- [ ] Panel de seguridad en Nexora Desktop

## 3. Gaming Engine
- Parcial: perfil game en nexora-perf / nexora-hwprofile (sysctl, scx_lavd).
- Todo lo demas pendiente: deteccion de juegos, perfiles por juego, NGNE,
  latencia, DNS adaptativo, prioridades de red, monitor de rendimiento,
  integracion Steam y NKE.

## 4. Stealth - privacidad y aislamiento
- [x] Modo Stealth con niveles Lite / Balanced / Advanced / Isolated
- [x] Tor Manager (nexora-tor, torrc.nexora, unidad systemd)
- [ ] Integracion con Tor Browser
- [ ] Aislamiento de sesiones (parcial via Cell)
- [ ] Perfiles de privacidad
- [ ] Centro de privacidad
- [ ] Monitor de conexiones
- [x] Proteccion contra filtraciones DNS (DNSPort 5353 + kill-switch)
- [ ] Gestion de metadatos
- [ ] Sandbox para aplicaciones (existente: Cell; pendiente integracion Stealth)
- [ ] Gestion de VPN
- [ ] Auditoria de privacidad
- [ ] Gestion configurable de datos y sesiones

## 5. Forge - desarrollo
- Todo pendiente: entornos por proyecto, herramientas bajo demanda, gestor de
  compilaciones, integracion NKE.

## 6. Office / Study
- Parcial: perfil office (swappiness 180, scx_bpfland, bajo consumo).
- Pendiente: instalacion/configuracion LibreOffice, integracion Obsidian,
  gestor de documentos, tareas adaptativas, swap adaptativo, NKE.

## 7. Hacking / Cybersecurity
- Todo pendiente: laboratorios aislados, auditoria, analisis de redes
  autorizadas, informes, niveles de herramientas, registro de operaciones.

## 8. Multimedia
- Todo pendiente: reproductor propio, biblioteca, listas, controles globales.

## 9. Nexora Desktop
- Todo pendiente: validacion GTK3, refinamiento XFCE, polkit, centros de
  actualizaciones y aplicaciones, integraciones visuales, monitorizacion,
  notificaciones, accesibilidad, revision UX/UI, recuperacion de sesion.

## 10. Red y conectividad
- [x] NetWall (parcial: cgroups + nftables + mapa eBPF)
- Pendiente: DNS inteligente, perfiles por app, VPN, monitor de trafico,
  diagnostico y recuperacion automatica, NGNE, validacion en hardware real.

## 11. IA y agentes
- Parcial: Guardian con punto de enganche llama.cpp.
- Pendiente: Model Manager, seleccion automatica, requisitos RAM/VRAM,
  coordinacion de agentes, centros de agentes y modelos.

## 12. Watchdogs, daemons y mantenimiento
- Parcial: nexora-doctor (5 comprobaciones + --auto), timers nexora-doctor y
  nexora-lens, limites MemoryMax en daemons.
- Pendiente: validacion en hardware real, supervision cruzada de servicios,
  mantenimiento programado completo, prevencion de bucles de reinicio,
  comprobacion de servicios huerfanos.

## 13. Distribucion e instalador
- [x] ISO reproducible construida por CI (archiso + GitHub Actions, job iso)
- [x] Instalador propio nexora-installer (sin archinstall): modo interactivo y
      --auto no interactivo, GPT (ESP o BIOS boot), A/B en btrfs con @root-b
      como instantanea identica desde el inicio, GRUB con entrada de respaldo
      @root-b, region es_ES y teclado es, registro en /var/log
- Parcial: imagen de recuperacion (recovery/), PKGBUILD del kernel
- Pendiente: arranque validado en QEMU y hardware fisico, instalador grafico,
  systemd-boot, recuperacion ante instalaciones fallidas, primer arranque,
  ARM64, tablets, firmware

## 14. Calidad, seguridad y testing
- Todo pendiente. Objetivos: >= 1500 pruebas por modo; >= 200 por
  funcionalidad nueva o modificada; unitarias, integracion, regresion,
  seguridad y rendimiento; prohibidos tests simulados como sustituto de
  validaciones reales y continue-on-error / || true para ocultar fallos.

## 15-17. Reglas, orden e informe
Reglas obligatorias por implementacion, fases de desarrollo y plantilla de
informe por ZIP: ver README.md y los criterios fijados en la hoja de ruta.
