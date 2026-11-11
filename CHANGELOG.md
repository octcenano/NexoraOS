# Changelog

## 0.3.0-beta

### Añadido
- `nexora.watchdog`: supervisión ligera del core (`nexora status`, `nexora-watchdog --loop` para systemd). Comprobaciones reales (config, aislamiento, vault), recuperación acotada (`max_restarts`, cooldown), registro de eventos acotado y salida JSON. Unidades systemd de sistema y usuario opcionales (`packaging/systemd/`), no habilitadas automáticamente.
- Modo Security real: `nexora.agents.security.SecurityAgent` y `nexora audit` — auditoría defensiva de **solo lectura** (configuración, vault, permisos de user.json, sockets en escucha vía /proc, ficheros escribibles por otros). Sin capacidades ofensivas.
- `nexora.core.permissions.ToolPolicy`: herramientas permitidas por modo; operaciones sensibles (red externa, ejecutar comandos, escribir fuera del proyecto, memoria de otro agente) exigen aprobación explícita (`ApprovalRequiredError`).
- `LocalAIEngine.list_models()`: detección de modelos en Ollama (`/api/tags`) y backends compatibles con OpenAI (`/v1/models`), con etiquetado simulado y errores controlados.
- Detección de GPU (`/sys/class/drm`) y almacenamiento libre (`statvfs`) en `core.profiles`; `nexora profile` los muestra.
- `core.config`: rechazo de claves de primer nivel desconocidas, validación de tipos de contenedores y `write_user_config()` (valida antes de escribir, directorio 700, archivo 600, escritura atómica con fsync).
- CLI: comandos `status` y `audit`; `modes` muestra el estado real de cada modo (stub/basic); mensajes de error consistentes.
- Tests nuevos: watchdog (9), security (4), tool policy (5), config extendida (7), `list_models` (4), perfiles/hardware extendidos (12) y casos de error (config corrupta, backend caído, permisos insuficientes).
- CI ampliada: Python 3.10 y 3.12, `compileall`, `pip check`, instalación limpia del wheel y arranque desde `/tmp`, ShellCheck, `bash -n` y gitleaks.

### Corregido
- El perfil archiso no era válido (secciones `[initcpio]`/`[efi]` inventadas, faltaban `pacman.conf`, `arch`, `airootfs_image_type` y `file_permissions` coherentes): reescrito según el formato actual de archiso.
- `scripts/build-iso.sh` asumía todo instalado y no verificaba nada: ahora comprueba requisitos, valida el perfil, verifica la ISO resultante (sha256, `file`, isoinfo) y explica cada error.
- `PKGBUILD` usaba un tarball por tag con `sha256sums=('SKIP')` y un nombre de directorio frágil (`NexoraOS-$pkgver`): ahora usa fuente git fijada por tag (`#tag=v$pkgver`), que es verificable por SHA de commit, e instala las unidades systemd.
- `nexora profile` imprimía valores fijos si fallaba la detección: mantiene el fallback seguro pero ahora también detecta GPU y almacenamiento.

### Pendiente (honesto)
- ISO no generada ni verificada en este entorno (sin mkarchiso ni red de paquetes).
- Tests no ejecutados localmente (sin intérprete Python disponible); los ejecuta CI en 3.10 y 3.12.
- OAuth real, GUI, sandbox de procesos, Open-Meteo en vivo y `keyring` real siguen pendientes.

## 0.2.0-beta (revisado)

Corrige el paquete anterior, cuyo código no coincidía con el documento de traspaso y cuya suite de tests no arrancaba.

### Corregido
- Los tests importaban `ModeRegistry`, `calculate_hybrid_profile` y `BaseAgent`, que no existían; `AccountHub` y `BrowserConnector` tenían otra API distinta a la usada por los tests. Ahora existen y los 9 tests originales pasan sin modificarse.
- `MeteorologyAgent` importaba una clase inexistente y devolvía datos fijos presentados como "observación verificada". Ahora los datos simulados se etiquetan `simulated: True` y existe un proveedor real (Open-Meteo, opt-in).
- `LocalAIEngine` afirmaba soportar Ollama/llama.cpp/LocalAI pero solo devolvía texto simulado, y `is_connected` era siempre `True`. Ahora implementa los tres backends.
- `SecureVault` era un diccionario sin política ni validación; ahora tiene backends explícitos y no filtra valores en `repr`.
- La CLI usaba funciones que no existían y valores fijos (4 núcleos, 8 GB); ahora detecta el hardware.
- `defaults.json` y `pyproject.toml` seguían en 0.1; ahora la versión sale de `nexora.__version__`.
- Faltaban `__init__.py` en 4 subpaquetes; el zip tenía una carpeta duplicada anidada.
- `diagnostics.health` devolvía estados fijos; ahora hace comprobaciones reales (aislamiento, config, vault, motor IA, navegadores).

### Añadido
- `core.config` (carga y validación; rechaza secretos), `AgentMessage` y `share_with` con aprobación explícita, estados y permisos reales en el Account Hub, comandos CLI `health`, `weather`, `ask`, opciones `dashboard --mode/--json`, 66 tests nuevos.
- `IsolatedAgent` se sustituye por `BaseAgent` (con memoria `remember/recall`).
