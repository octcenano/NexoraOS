# NEXORA OS

Entorno modular de agentes (plano de control en Python) pensado para convertirse en una distribución ligera basada en Arch Linux. Estado actual: beta 0.4, prototipo ejecutable por CLI. No es todavía un sistema operativo completo ni una ISO arrancable verificada.

## Estado real (resumen honesto)

| Área | Estado |
| --- | --- |
| CLI (`nexora`) | Implementada y probada por tests unitarios |
| Modos oficiales (gaming, hacking, office, stealth, forge) | Registrados con memoria aislada, política de herramientas e intensidades 1/2/3/full respaldadas por políticas reales del núcleo adaptativo. Los agentes específicos de cada modo están pendientes (estado declarado: stub) |
| Nexora Desktop | Modelos completos (Shell, Dashboard, Mode Center, NKE Control, Hub, System Center) con datos reales y estados explícitos; vista GTK3 implementada con importación diferida (no ejecutada aún en entorno gráfico). Base: XFCE + Nexora Desktop |
| Agentes especializados | Meteorology (observación meteorológica) y Security (auditoría defensiva de solo lectura) con lógica propia; no son modos |
| Núcleo adaptativo | Inventario real del sistema, niveles level1/2/3/full y planes de asignación reversibles |
| NKE (Kernel Engine) | Motor en espacio de usuario sobre PSI, /proc, /sys, cgroups v2 y systemd; categorías A/B/C con rollback y API de aprobación. No verificado en un host real |
| Motor IA local | Ollama y OpenAI-compatible implementados contra loopback; probado con transporte falso en tests y con mock. No probado contra Ollama real |
| Bóveda de secretos | Memoria por defecto; keyring del SO si python-keyring está disponible. Sin secretos en texto plano |
| Watchdog | Implementado (pasada única, diagnóstico, bucle acotado). Unidad systemd incluida, no verificada en un sistema real |
| ISO live (archiso) | Perfil y script de construcción corregidos, pila XFCE incluida. ISO NO construida en este entorno; arranque NO verificado |
| Instalador | Script en la ISO (pendiente de verificar). Instalador gráfico: no existe |

## Instalación rápida (desarrollo)

```bash
python -m pip install .
nexora --help
nexora health
nexora modes
nexora desktop --json      # modelo completo de Nexora Desktop
nexora desktop --gtk       # ventana GTK3 (requiere python-gobject y sesión gráfica)
nexora-watchdog --diagnose
```

Requisitos: Python 3.10 o superior. Opcionales: `python-keyring`, `ollama`, `python-gobject` + `gtk3` (Nexora Desktop), `libnotify`.

## Configuración

- Predeterminada: `config/defaults.json` (instalada en `/usr/share/nexora/config/`).
- Usuario: `~/.config/nexora/user.json` (ver plantilla `config/user.example.json`). La configuración del usuario prevalece sobre la predeterminada.
- Nunca guardes secretos en `user.json`: usa la bóveda.

## Modos e intensidades

```bash
nexora modes                        # lista los cinco modos oficiales
nexora mode gaming                  # política efectiva del modo
nexora mode gaming --intensity 3    # fija la intensidad (1, 2, 3, full)
```

## Nexora Desktop

XFCE + Nexora Desktop: XFCE es la base; la capa Nexora añade Dashboard, Mode Center, NKE Control, Hub y System Center. Detalles en `docs/DESKTOP.md`. La sesión con recuperación automática al escritorio XFCE estándar está en `packaging/xfce/nexora-session.sh`.

## Motor IA

Por defecto el motor es `local_mock` (respuestas claramente marcadas como simuladas). Para usar Ollama en local:

```json
{ "ai_engine": { "backend": "ollama", "model": "llama3.2:1b" } }
```

Solo se aceptan endpoints de loopback salvo `allow_remote=true` explícito. Nexora no descarga modelos ni envía datos a servicios remotos sin consentimiento.

## Seguridad

- Auditoría defensiva de solo lectura: `nexora audit`.
- Nexora Desktop nunca se ejecuta como root; sin comandos arbitrarios desde la interfaz.
- Sin extracción de credenciales de navegadores, sin capacidades ofensivas, sin ejecución de comandos generados por modelos.

## Documentación

- `docs/INSTALL.md` (instalación y desinstalación)
- `docs/ARCHITECTURE.md` (arquitectura)
- `docs/MODES.md` (modos oficiales e intensidades)
- `docs/NKE.md` (Kernel Engine)
- `docs/DESKTOP.md` (Nexora Desktop e integración XFCE)
- `docs/DEVELOPMENT.md` (desarrollo y pruebas)
- `docs/DIAGNOSTICS.md` (diagnóstico y watchdog)
- `docs/QA_REPORT.md` (informe de calidad)
- `docs/ROADMAP.md` (plan)

## Licencia

MIT. Ver `LICENSE`.
