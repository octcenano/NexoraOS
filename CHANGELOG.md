# Changelog

## Beta 0.4.0: cierre de beta y procesos (2026-11-12)

### CI/CD
- CI verde con la suite ampliada: tests (257), lint (ShellCheck, bash -n, gitleaks), package (wheel) e iso-build (ISO real construida en el contenedor archlinux:base privilegiado; runs 40 a 42). Los runs posteriores al fix de meteorología quedaron en cola por saturación de runners del plan gratuito; el estado exacto por run se mantiene en docs/QA_REPORT.md.
- Corregida la última incidencia de tests: la expectativa de meteorología contenía doble codificación UTF-8 (CÃ³digo) y no coincidía con la salida correcta del proveedor (Código); corregido el test en 8643187 tras corregir el motor en e24b5c0.
- Diagnóstico de fallos legible: los tres jobs de CI publican un issue con los logs al fallar; iso-build lo hace vía API con curl porque gh no existe en el contenedor Arch. Los issues de diagnóstico generados durante la depuración están cerrados.
- Nuevo workflow de seguridad (`.github/workflows/security.yml`): bandit (análisis estático), pip-audit (vulnerabilidades en dependencias, semanal y en cada push) y gitleaks sobre el historial completo (secretos). Cada hallazgo se publica como issue. Los tres análisis están en verde (runs 10 y 11): sin hallazgos de bandit ni gitleaks y sin vulnerabilidades conocidas en dependencias, tras excluir el paquete local nexora-os del freeze (no está publicado en PyPI) y auditar el resto con --no-deps.
- Nuevo workflow de release (`.github/workflows/release.yml`): al crear un tag v* construye el wheel y la ISO, genera el sha256 y crea un release borrador con ambos. La publicación es manual: nadie publica una beta sin revisión.

### Nexora System Center (secciones completadas)
- Usuarios: listado real de cuentas desde /etc/passwd (solo lectura), separando cuentas humanas de las de sistema. La edición de cuentas queda fuera de la beta y lo declara.
- Actualizaciones: consulta real de paquetes pendientes con pacman -Qu (solo lectura, sin shell, con tiempo de espera).
- Acciones privilegiadas cerradas: la actualización del sistema se lanza exclusivamente vía pkexec con una lista blanca fija de argv (sin interpolación); la autenticación la decide polkit. La interfaz nunca construye comandos dinámicos ni toca contraseñas.
- Tests nuevos: passwd real y sintético, salida de pacman -Qu simulada con script fijo, catálogo de acciones privilegiadas, rechazo de acciones desconocidas y contexto deshabilitado, ausencia de pkexec declarada como unavailable.

## En desarrollo (Nexora Desktop, 2026-11-11)

### Nexora Desktop (nuevo)
- Nuevo paquete `nexora/desktop` con separación estricta modelo/vista: los modelos son Python puro, testables sin entorno gráfico; la vista GTK3 (`gtkui.py`) se importa de forma diferida y su ausencia produce un error claro, no un fallo silencioso.
- **Nexora Shell** (`shell.py`): índice real de aplicaciones instaladas (parseo de archivos .desktop de XDG), búsqueda global (aplicaciones + comandos Nexora fijos), diseño declarativo del panel con plugins reales de xfce4-panel, notificaciones vía notify-send sin shell y escritorios virtuales declarativos para xfwm4.
- **Nexora Dashboard** (`dashboard.py`): CPU, RAM y swap desde /proc/meminfo, GPU, temperaturas de hwmon, almacenamiento, interfaces de red, batería, procesos top por RSS real (/proc), estado de servicios con systemctl y actividad de Core/NKE. Cada sección declara su estado: ok, no_data, unavailable o error; ninguna cifra inventada.
- **Nexora Mode Center** (`mode_center.py`): activar, combinar y desactivar los cinco modos oficiales con intensidades 1/2/3/full; cambios previstos calculados con build_allocation (plan real, no decorativo); conflictos declarativos entre modos (stealth frente a gaming/forge); recuperación de la configuración anterior mediante instantánea reversible.
- **Nexora NKE Control** (`nke_control.py`): estado del motor, capacidades del kernel, eBPF con degradación declarada, catálogo de políticas con explicación, acciones supervisadas pendientes con aprobación/rechazo, deshacer, historial y huella propia del NKE (duración media y máxima de ciclo).
- **Nexora Hub** (`hub.py`): agentes (modos y especialistas) con estado real de ejecución, modelos IA por proveedor sondeando solo endpoints de loopback (Ollama, llama.cpp, LocalAI; OpenAI-compatible) y herramientas instaladas por categoría XDG.
- **Nexora System Center** (`system_center.py`): catorce secciones que reutilizan herramientas de XFCE y Linux con lista blanca de comandos fijos y ejecución sin shell.
- **Orquestador** (`app.py`): ciclo de vida start/shutdown con registro de eventos acotado, rechazo explícito de ejecución como root, modelo completo serializable para la GUI y arranque GTK diferido.
- **Vista GTK3** (`gtkui.py`): ventana con pestañas por módulo, tema oscuro por defecto, acento y CSS del tema Nexora-Dark si está instalado. No ejecutada aún en entorno gráfico (sin PyGObject en CI): probada la ausencia controlada.
- **API del NKE ampliada** (`engine.py`): `last_supervised()`, `approve_proposal()`, `reject_proposal()` y `undo_last()`.
- **Integración XFCE** (`packaging/xfce/`): sesión `nexora-session.sh` con recuperación, autostart, scripts xfconf de panel y apariencia, y tema GTK3 oscuro Nexora-Dark.
- **Empaquetado**: PKGBUILD con dependencias opcionales de escritorio; la ISO incluye la pila XFCE mínima.
- **CLI**: `nexora desktop --json` y `--gtk`; comando `nexora-desktop` como entry point del paquete.
- **Tests**: `tests/test_desktop.py` (índice y búsqueda, estados del dashboard, procesos reales, validación de servicios, mode center con plan y rollback, NKE control, hub con sondeo loopback, lista blanca, ciclo de vida y rechazo de root).

## En desarrollo (Fase 5: modos oficiales, 2026-11-11)

### Cinco modos oficiales con intensidades
- `nexora/core/registry.py`: los modos oficiales son gaming, hacking, office, stealth y forge, con intensidades 1, 2, 3 y full respaldadas por las LevelPolicy reales.
- Creator deja de estar registrado como modo. Meteorology y Security quedan como agentes especializados.
- CLI: `nexora mode <nombre> [--intensity 1|2|3|full]` y `nexora modes`.
- Configuración: `modes_enabled` actualizado en `config/defaults.json` y su copia empaquetada.
- Corregido `packaging/archiso/profiledef.sh`: `buildmodes=('iso')`.

## En desarrollo (Nexora Kernel Engine, 2026-11-11)

### NKE — Nexora Kernel Engine (nuevo)
- Motor de optimización en espacio de usuario sobre /proc, /sys, PSI, cgroups v2 y systemd.
- Detección real de capacidades; monitor adaptativo (2 s a 60 s); hallazgos por umbrales; políticas A/B/C con Safety Controller y rollback; cooldown y límites por ciclo; Kernel Manager y Module Manager de solo lectura.
- CLI `nexora nke` y `nexora-nke`; unidad systemd endurecida; tests y `docs/NKE.md`.

## 0.4.0-beta (2026-11-11)

### Watchdog, motor IA, Security, build y CI
- Watchdog: modo diagnóstico, historial, anti-bucle, unidades systemd endurecidas.
- Motor IA: list_models, has_model, select_model, detect_backends (solo loopback), errores como estado.
- Agente Security: inventario de sockets, antigüedad de sincronización de pacman, informe atómico 600.
- Build: scripts/build-iso.sh con verificación sha256 y El Torito; PKGBUILD 0.4.0.
- CI: gitleaks fijado a v8.21.2; ShellCheck vía apt; job de ISO en contenedor archlinux:base.

## 0.3.0-beta

- Rama de recuperación, endurecimiento del vault, permisos por herramienta, dashboard de modos, CLI ampliada, perfil archiso y PKGBUILD iniciales, workflow CI.

## 0.2.0-beta

- Prototipo inicial: CLI, agentes base y meteorología, core, diagnóstico de salud, dashboard de texto.
