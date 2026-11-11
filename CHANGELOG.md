# Changelog

## En desarrollo (Nexora Desktop, 2026-11-11)

### Nexora Desktop (nuevo)
- Nuevo paquete `nexora/desktop` con separación estricta modelo/vista: los modelos son Python puro, testables sin entorno gráfico; la vista GTK3 (`gtkui.py`) se importa de forma diferida y su ausencia produce un error claro, no un fallo silencioso.
- **Nexora Shell** (`shell.py`): índice real de aplicaciones instaladas (parseo de archivos .desktop de XDG), búsqueda global (aplicaciones + comandos Nexora fijos), diseño declarativo del panel con plugins reales de xfce4-panel, notificaciones vía notify-send sin shell y escritorios virtuales declarativos para xfwm4.
- **Nexora Dashboard** (`dashboard.py`): CPU, RAM y swap desde /proc/meminfo, GPU, temperaturas de hwmon, almacenamiento, interfaces de red, batería, procesos top por RSS real (/proc), estado de servicios con systemctl y actividad de Core/NKE. Cada sección declara su estado: ok, no_data, unavailable o error; ninguna cifra inventada.
- **Nexora Mode Center** (`mode_center.py`): activar, combinar y desactivar los cinco modos oficiales con intensidades 1/2/3/full; cambios previstos calculados con build_allocation (plan real, no decorativo); conflictos declarativos entre modos (stealth frente a gaming/forge); recuperación de la configuración anterior mediante instantánea reversible.
- **Nexora NKE Control** (`nke_control.py`): estado del motor, capacidades del kernel, eBPF con degradación declarada, catálogo de políticas con explicación, acciones supervisadas pendientes con aprobación/rechazo, deshacer, historial y huella propia del NKE (duración media y máxima de ciclo).
- **Nexora Hub** (`hub.py`): agentes (modos y especialistas) con estado real de ejecución, modelos IA por proveedor sondeando solo endpoints de loopback (Ollama, llama.cpp, LocalAI; OpenAI-compatible) y herramientas instaladas por categoría XDG.
- **Nexora System Center** (`system_center.py`): catorce secciones que reutilizan herramientas de XFCE y Linux con lista blanca de comandos fijos y ejecución sin shell; las secciones que requieren privilegios (usuarios, actualizaciones) se declaran pendientes en lugar de mostrar botones falsos.
- **Orquestador** (`app.py`): ciclo de vida start/shutdown con registro de eventos acotado, rechazo explícito de ejecución como root, modelo completo serializable para la GUI y arranque GTK diferido.
- **Vista GTK3** (`gtkui.py`): ventana con pestañas por módulo, tema oscuro por defecto, acento y CSS del tema Nexora-Dark si está instalado. No ejecutada aún en entorno gráfico (sin PyGObject en CI): probada la ausencia controlada.
- **API del NKE ampliada** (`engine.py`): `last_supervised()`, `approve_proposal()` (valida categoría B, reversibilidad y pendencia; registra la decisión), `reject_proposal()` y `undo_last()`. La interfaz no ejecuta operaciones privilegiadas: pasa por esta API controlada.
- **Integración XFCE** (`packaging/xfce/`): sesión `nexora-session.sh` con recuperación (tres fallos en 60 s devuelven el escritorio XFCE estándar y limpian procesos), autostart, scripts xfconf de panel y apariencia, y tema GTK3 oscuro Nexora-Dark.
- **Empaquetado**: PKGBUILD con dependencias opcionales de escritorio e instalación de sesión/tema/autostart; la ISO incluye la pila XFCE mínima (xfce4, whiskermenu, thunar, networkmanager, pipewire, python-gobject, gtk3, libnotify).
- **CLI**: `nexora desktop --json` (modelo completo) y `--gtk` (ventana); comando `nexora-desktop` como entry point del paquete.
- **Tests**: `tests/test_desktop.py` (índice y búsqueda, estados del dashboard, procesos reales, validación de servicios, mode center con plan y rollback, NKE control con aprobaciones rechazadas sin pendencia, hub con sondeo loopback, lista blanca del system center, ciclo de vida y rechazo de root).

## En desarrollo (Fase 5: modos oficiales, 2026-11-11)

### Cinco modos oficiales con intensidades
- `nexora/core/registry.py`: los modos oficiales son ahora gaming, hacking, office, stealth y forge, cada uno con niveles de intensidad 1, 2, 3 y full respaldados por las LevelPolicy reales del núcleo adaptativo (level1/level2/level3/full).
- Creator deja de estar registrado como modo (no es un modo oficial). Meteorology y Security quedan como agentes especializados o funcionalidad transversal, no como modos principales.
- CLI: nuevo comando `nexora mode <nombre> [--intensity 1|2|3|full]` que muestra y fija la política efectiva; `nexora modes` lista los cinco modos oficiales y los agentes especializados por separado.
- Dashboard: widget de intensidad del modo activo y método `set_intensity` validado.
- Configuración: `modes_enabled` actualizado a los cinco modos oficiales en `config/defaults.json` y en la copia empaquetada.
- Tests nuevos: `tests/test_modes_official.py` (modos exactos, especialistas fuera del registro, validación de intensidades, mapeo a LevelPolicy reales, coordinador, política de hacking sin autonomía ofensiva). Tests de CLI, dashboard y core actualizados.
- Corregido `packaging/archiso/profiledef.sh`: el bloque INI inválido `[build] options=()` se sustituye por `buildmodes=('iso')` (profiledef.sh se ejecuta como Bash).

## En desarrollo (Nexora Kernel Engine, 2026-11-11)

### NKE — Nexora Kernel Engine (nuevo)
- Motor de optimización en espacio de usuario sobre interfaces estándar del kernel: `/proc`, `/sys`, PSI, cgroups v2 y systemd. No modifica el kernel ni carga módulos.
- `nexora/nke/capabilities.py`: detección real de capacidades (PSI, cgroups v2, eBPF, cpufreq, swap, Secure Boot). Si una capacidad no existe, no se proponen acciones que la requieran.
- `nexora/nke/monitor.py`: monitor con sondeo adaptativo (2 s a 60 s; se ralentiza en reposo y vuelve al mínimo con presión).
- `nexora/nke/analyzer.py`: hallazgos por umbrales (presión de memoria/CPU/IO, swap thrashing, poca RAM) con acciones sugeridas.
- `nexora/nke/policy.py`: catálogo de acciones con tres categorías. A (automática, reversible), B (supervisada: propuesta que exige aprobación humana) y C (protegida: nunca ejecutada por NKE, solo listada como propuesta informativa).
- `nexora/nke/safety.py`: Safety Controller con validación, rollback automático y rechazo de la categoría C.
- `nexora/nke/engine.py`: ciclo completo con cooldown por objetivo (300 s), máximo 3 acciones automáticas por ciclo, detección de degradación y rollback automático. Mide su propia duración.
- `nexora/nke/kernel_extension.py`: Kernel Manager, Module Manager (solo lectura; la carga de módulos es siempre propuesta C), Hardware Interface y ExtensionAPI de consultas cerradas para agentes.
- CLI: `nexora nke {status,diagnose,history}` y comando `nexora-nke` (`--once`, `--loop`, `--json`, protección anti-bucle).
- Dashboard: panel `Kernel Engine` con release, capacidades y estado del motor.
- Watchdog: nuevo componente `nke` (verifica la lectura de capacidades).
- Unidad systemd `nexora-nke.service` con DynamicUser, MemoryMax=80M, CPUQuota=2% y endurecimiento completo.
- Tests: `tests/test_nke.py` (capacidades, monitor, analizador, políticas, seguridad, motor, rollback, huella, extensión de kernel, integración CLI/dashboard) y `test_watchdog.py` actualizado.
- Documentación: `docs/NKE.md`.

## En desarrollo (Fase 1 y Fase 2 del plan adaptativo, 2026-11-11)

### Fase 1 — Estabilización
- Corregido el test de cooldown del watchdog (el reloj falso arrancaba en 0.0 y el primer intento caía siempre dentro del cooldown).
- Eliminada la ocultación de errores en CI y en build-iso.sh (sin `|| true` innecesarios ni `continue-on-error` en el job de ISO).
- CI: los tests fallidos y los hallazgos de ShellCheck se publican como anotaciones del job (diagnóstico sin necesidad de sesión).
- Job de ISO real en contenedor archlinux:base con las dependencias correctas (python-setuptools, python-wheel): ahora puede fallar y debe fallar si la construcción falla.

### Fase 2 — Núcleo adaptativo (nuevo)
- `nexora/core/resources.py`: inventario real del sistema (CPU, RAM, GPU, temperaturas, batería, almacenamiento, red) sin dependencias; niveles level1/level2/level3/full como políticas verificables (agentes concurrentes, RAM máxima por modelo, pesos de CPU); perfiles híbridos con modo primario priorizado y planes de asignación reversibles (no tocan el sistema hasta apply()).
- `nexora/core/coordinator.py`: coordinador de agentes con tareas estructuradas, validación de permisos por ToolPolicy, aprobación explícita para herramientas sensibles, historial acotado y enrutado de mensajes con el contrato AgentMessage existente.
- Tests: test_resources.py (inventario, niveles, reparto híbrido, batería, compatibilidad) y test_coordinator.py (permisos, denegaciones, historial, comunicación).

## 0.4.0-beta (2026-11-11)

### Watchdog
- Nuevo modo diagnóstico `--diagnose` (y `--json`): informe sin efectos secundarios con recomendaciones, historial de incidencias y contadores de reinicio.
- Historial de incidencias acotado (transiciones sano -> degradado por componente).
- Protección anti-bucle en modo bucle: los errores internos no derriban el proceso, pero N pasadas consecutivas con error provocan una salida controlada (código 3) para que systemd aplique su propia política de reinicio.
- Unidades systemd con límites de recursos (MemoryMax=150M, CPUQuota=5%) y endurecimiento (NoNewPrivileges, ProtectSystem=strict, ProtectKernelTunables, ProtectControlGroups).

### Motor IA local
- `list_models()`: lista modelos reales del backend (Ollama `/api/tags`, OpenAI-compatible `/v1/models`); el mock lista solo su modelo simulado.
- `has_model(model)`: comprueba disponibilidad sin descargar nada.
- `select_model(model)`: selección de modelo por usuario.
- `detect_backends()`: sondeo solo de endpoints de loopback por defecto; devuelve disponibilidad, endpoint y modelos por backend.
- Errores de conexión y respuestas inesperadas devuelven `status: error` en lugar de lanzar excepciones.

### Agente Security
- Inventario de sockets en escucha (familia y puerto, desde /proc) en lugar de un simple conteo.
- Comprobación de antigüedad de la sincronización de pacman (aviso si supera 14 días).
- Campo `recommendations` en el informe de auditoría.
- `write_report(report, path)`: única escritura del agente, explícita, atómica y con permisos 600.

### Build y packaging
- `scripts/build-iso.sh`: elimina ISOs y wheels antiguos antes de compilar, falla si `dist/` tiene más de un wheel, verifica que la ISO generada es única y válida (sha256, file, El Torito cuando isoinfo está disponible).
- Comprobaciones previas: python, python-build, archivos obligatorios del perfil archiso.
- PKGBUILD: pkgver 0.4.0. Perfil archiso: iso_version 0.4.0. Ahora instala también `nexora-nke.service`.

### CI
- Gitleaks fijado a la versión v8.21.2 (binario oficial) en lugar de una acción flotante.
- ShellCheck vía apt (versión gestionada por Ubuntu) con tolerancia a ausencia de scripts.
- Job de construcción de ISO en contenedor archlinux:base.

### Tests
- Tests nuevos y actualizados: watchdog (cooldown, agotamiento, incidencias, diagnóstico), motor IA (select_model, has_model, list_models, detect_backends, backend caído, respuesta inesperada), agente Security (inventario de puertos, recomendaciones, informe atómico 600).

## 0.3.0-beta

- Rama de recuperación `beta-0.3-recovery`, endurecimiento del vault, permisos por herramienta, dashboard de modos, CLI ampliada, perfil archiso y PKGBUILD iniciales, workflow CI.

## 0.2.0-beta

- Prototipo inicial: CLI, agentes base y meteorología, connectors de cuenta y navegador, core (config, permissions, profiles, registry, vault), diagnóstico de salud, dashboard de texto.
