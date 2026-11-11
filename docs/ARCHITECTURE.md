# Arquitectura NEXORA OS (Beta 0.2)

## Capas
1. **NEXORA Core**: configuraciÃ³n (`core.config`), registro de modos (`core.registry`), permisos (`core.permissions`), perfiles (`core.profiles`), motor IA local (`core.ai_engine`), vault (`core.vault`) y diagnÃ³stico (`diagnostics.health`).
2. **Mode Runtime**: carga un modo sin mezclar su memoria privada con la de otros modos.
3. **Agent Runtime**: un agente por modo (`agents.base.BaseAgent`). Solo meteorologÃ­a tiene lÃ³gica propia; el resto son agentes base (stub).
4. **Account Hub**: catÃ¡logo de conexiones y permisos revocables.
5. **Hardware/Profile Manager**: detecciÃ³n automÃ¡tica y sugerencias; el usuario puede fijar el perfil o los lÃ­mites.
6. **UI Runtime**: modelo de estado del dashboard + vista de terminal. La GUI grÃ¡fica consumirÃ¡ `render_layout()`.
7. **System Integration**: futura integraciÃ³n con systemd, paquetes, escritorio e instalador (no implementada).

## Aislamiento de agentes
Cada agente tiene su propia memoria privada (`agents/<mode>/`). No hay memoria compartida. El intercambio pasa por `AgentMessage` (origen, destino, propÃ³sito y datos seleccionados) y solo se emite con `user_approved=True`. El receptor lo recibe en una **bandeja de entrada**, nunca en su memoria privada.

> Alcance: el aislamiento es lÃ³gico (espacios de nombres y API dentro de un mismo proceso). No es una frontera de seguridad frente a cÃ³digo malicioso. El aislamiento por procesos/permisos del SO pertenece a Beta 0.3+.

## Secretos
- La configuraciÃ³n rechaza secretos (`core.config.find_secret_like`).
- `SecureVault` es la Ãºnica vÃ­a prevista para credenciales. Backend por defecto: RAM. Backend persistente: almacÃ©n del SO vÃ­a `keyring`. No hay criptografÃ­a propia.
- El Account Hub solo guarda `secret_ref` (nombre de la entrada en el vault), nunca el secreto.

## Privacidad y red
- TelemetrÃ­a desactivada.
- El motor IA solo acepta endpoints locales salvo `allow_remote` explÃ­cito, y no usa proxies.
- Las consultas de red del agente meteorolÃ³gico son opt-in.

## Account Hub y navegadores
Firefox y LibreWolf son opciones de primera clase (`both` = ambos). La conexiÃ³n se implementarÃ¡ preferentemente con OAuth/API oficial. Una integraciÃ³n local de navegador deberÃ¡ usar mecanismos documentados y consentimiento explÃ­cito. No se extraerÃ¡n cookies, contraseÃ±as ni tokens de perfiles. Hoy solo se detecta si hay ejecutables en el PATH.

## Perfiles hÃ­bridos
El sistema detecta recursos y recomienda un perfil (`compact`, `balanced`, `expanded`). Los ajustes manuales tienen prioridad y, si superan lo recomendado, se muestra un aviso y se puede revertir con `--profile auto`. NingÃºn perfil debe aplicar cambios de kernel, red, energÃ­a o seguridad sin mostrar el cambio y permitir revertirlo. Los lÃ­mites por perfil son orientativos, no medidos.

## Servicios persistentes
Los watchdogs y demonios se instalarÃ¡n solo cuando exista una funciÃ³n concreta, consumo medido, polÃ­tica de reinicio y mecanismo de apagado. En Beta 0.2 siguen documentados, no desplegados.
