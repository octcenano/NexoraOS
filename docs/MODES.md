# Modos de NEXORA

| Modo | Estado | Herramientas declaradas |
|---|---|---|
| Forge | stub (solo registrado) | `local_ai` |
| Meteorology | funcionalidad básica | `local_ai`, `weather_simulated`, `weather_live_opt_in` |
| Security | funcionalidad básica | `local_ai`, `defensive_audit_readonly` |
| Creator | stub (solo registrado) | `local_ai` |
| Office | stub (solo registrado) | `local_ai` |

- **Forge**: desarrollo, proyectos, herramientas y modelos locales. Stub con memoria aislada.
- **Meteorology**: observación actual (simulada por defecto, Open-Meteo opt-in con `--live`). Sin alertas ni sondeos todavía.
- **Security**: auditoría defensiva de solo lectura (`nexora audit`): configuración, vault, permisos de archivos de usuario, sockets en escucha y ficheros escribibles por otros. Sin escaneo de red ni capacidades ofensivas.
- **Creator**: planificación y análisis de contenido digital. Stub.
- **Office**: documentos, estudio y productividad. Stub.

Cada modo tiene memoria privada, estado declarado (`stub`/`basic`) y una `ToolPolicy` que define qué herramientas puede usar; las operaciones sensibles exigen aprobación explícita del usuario. El núcleo común solo proporciona servicios transversales.
