# Arquitectura NEXORA OS (Beta 0.3)

## Capas
1. **NEXORA Core**: configuración (`core.config`), registro de modos (`core.registry`), permisos y política de herramientas (`core.permissions`), perfiles (`core.profiles`), motor IA local (`core.ai_engine`), vault (`core.vault`), watchdog (`nexora.watchdog`) y diagnóstico (`diagnostics.health`).
2. **Mode Runtime**: carga un modo sin mezclar su memoria privada con la de otros modos. Cada modo declara estado honesto (`stub`/`basic`) y sus herramientas (`ModeRegistry.tool_policy`).
3. **Agent Runtime**: un agente por modo (`agents.base.BaseAgent`). Meteorología y Security tienen lógica propia; Forge, Creator y Office son stub declarados como tal.
4. **Account Hub**: catálogo de conexiones y permisos revocables. Sin OAuth real todavía.
5. **Hardware/Profile Manager**: detección de CPU, RAM, GPU y almacenamiento; sugerencias automáticas que nunca imponen nada al usuario.
6. **UI Runtime**: modelo de estado del dashboard + vista de terminal renovada. La GUI futura consumirá `render_layout()`.
7. **System Integration**: watchdog opcional como unidad systemd (sistema y usuario), PKGBUILD y perfil archiso. Sin servicios residentes por defecto.

## Aislamiento de agentes
Cada agente tiene su memoria privada (`agents/<mode>/`). El intercambio pasa por `AgentMessage` (origen, destino, propósito y datos seleccionados) y solo se emite con `user_approved=True`. El receptor lo recibe en una **bandeja de entrada**, nunca en su memoria privada.

> Alcance: el aislamiento es lógico (espacios de nombres y API dentro de un mismo proceso). No es una frontera de seguridad frente a código malicioso. El sandbox de procesos pertenece a una beta posterior.

## Herramientas y permisos
- `ToolPolicy` (por modo): solo se pueden usar herramientas declaradas; `authorize_use()` lanza `PermissionError` si la herramienta no está permitida y `ApprovalRequiredError` si es sensible sin aprobación.
- Operaciones siempre sensibles (`SENSITIVE_TOOLS`): `network_remote`, `execute_commands`, `write_system`, `access_other_agent_memory`.
- El modo Security solo declara `defensive_audit_readonly`.

## Modo Security
Auditoría defensiva de solo lectura (`nexora audit`): validez de configuración, secretos en config, backend del vault, permisos de `user.json`, sockets en escucha (vía `/proc`) y ficheros escribibles por otros bajo `~/.config/nexora`. Sin escaneo de red, sin explotación, sin modificaciones.

## Secretos
- La configuración rechaza secretos y claves desconocidas (`core.config`).
- `SecureVault`: RAM por defecto; almacén del SO vía `keyring`. Sin criptografía propia.
- `write_user_config()` escribe de forma atómica con permisos 700 (directorio) y 600 (archivo).
- El Account Hub solo guarda `secret_ref`.

## Privacidad y red
- Telemetría desactivada.
- Motor IA: solo endpoints de loopback salvo `allow_remote` explícito; sin proxies; peticiones con timeout; no descarga modelos.
- Consultas de red del agente meteorológico opt-in (`--live`).

## Watchdogs
- `nexora.watchdog.Watchdog`: componentes con `health_check` y `recover` opcionales; reinicios acotados (`max_restarts`, cooldown), estados `ok/degraded/failed`, log acotado; nunca modifica configuración ni políticas.
- `nexora status`: una pasada; `nexora-watchdog --loop N`: para systemd.
- Unidades systemd endurecidas y no habilitadas automáticamente. Desinstalación documentada en las propias unidades y en `packaging/README.md`.

## Perfiles híbridos
Detección de CPU, RAM, GPU y almacenamiento libre sin dependencias externas. Sugerencia automática (`compact`/`balanced`/`expanded`) que el usuario puede anular; si el perfil elegido supera lo recomendado, se avisa y se puede revertir con `--profile auto`. Los límites son orientativos, no medidos.

## Construcción (base Arch)
- `packaging/arch/PKGBUILD`: fuente git fijada por tag; build con `python -m build`, check con unittest, instalación de config del sistema y unidades systemd.
- `packaging/archiso/`: perfil en formato archiso actual (profiledef.sh, pacman.conf, packages.x86_64, airootfs con hostname/motd e `install-nexora.sh`).
- `scripts/build-iso.sh`: comprobaciones previas, build del wheel, tests, mkarchiso y verificación posterior (sha256, `file`, isoinfo). Estado: no ejecutado aún (ver QA_REPORT).
