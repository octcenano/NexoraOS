# NEXORA OS

Entorno modular de agentes (plano de control en Python) pensado para convertirse en una distribución ligera basada en Arch Linux. Estado actual: beta 0.4, prototipo ejecutable por CLI. No es todavía un sistema operativo completo ni una ISO arrancable verificada.

## Estado real (resumen honesto)

| Área | Estado |
| --- | --- |
| CLI (`nexora`) | Implementada y probada por tests unitarios |
| Modos (forge, meteorology, security, creator, office) | Implementados como agentes con memoria aislada; security y meteorology con lógica propia, el resto básicos |
| Motor IA local | Ollama y OpenAI-compatible implementados contra loopback; probado con transporte falso en tests y con mock. No probado contra Ollama real |
| Bóveda de secretos | Memoria por defecto; keyring del SO si python-keyring está disponible. Sin secretos en texto plano |
| Watchdog | Implementado (pasada única, diagnóstico, bucle acotado). Unidad systemd incluida, no verificada en un sistema real |
| ISO live (archiso) | Perfil y script de construcción corregidos. ISO NO construida en este entorno (no hay mkarchiso); arranque NO verificado |
| Interfaz gráfica | Pendiente. Solo dashboard de texto |
| Instalador | Script en la ISO (pendiente de verificar). Instalador gráfico: no existe |

## Instalación rápida (desarrollo)

```bash
python -m pip install .
nexora --help
nexora health
nexora-watchdog --diagnose
```

Requisitos: Python 3.10 o superior. Opcional: `python-keyring`, `ollama`.

## Configuración

- Predeterminada: `config/defaults.json` (instalada en `/usr/share/nexora/config/`).
- Usuario: `~/.config/nexora/user.json` (ver plantilla `config/user.example.json`). La configuración del usuario prevalece sobre la predeterminada.
- Nunca guardes secretos en `user.json`: usa la bóveda (`nexora vault ...`).

## Motor IA

Por defecto el motor es `local_mock` (respuestas claramente marcadas como simuladas). Para usar Ollama en local:

```json
{ "ai_engine": { "backend": "ollama", "model": "llama3.2:1b" } }
```

Solo se aceptan endpoints de loopback salvo `allow_remote=true` explícito. Nexora no descarga modelos ni envía datos a servicios remotos sin consentimiento.

## Seguridad

- Auditoría defensiva de solo lectura: `nexora security audit`.
- Informe explícito: `nexora security report ruta/informe.json` (permisos 600).
- Sin extracción de credenciales de navegadores, sin capacidades ofensivas, sin ejecución de comandos generados por modelos.

## Documentación

- `docs/INSTALL.md` (instalación y desinstalación)
- `docs/ARCHITECTURE.md` (arquitectura)
- `docs/DEVELOPMENT.md` (desarrollo y pruebas)
- `docs/DIAGNOSTICS.md` (diagnóstico y watchdog)
- `docs/QA_REPORT.md` (informe de calidad)
- `docs/ROADMAP.md` (plan)

## Licencia

MIT. Ver `LICENSE`.
