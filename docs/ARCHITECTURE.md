# Arquitectura — NexoraOS

## Visión general

Plano de control en Python (paquete `nexora`) con agentes por modo, bóveda de secretos, permisos por herramienta, watchdog ligero, Nexora Kernel Engine (NKE) y empaquetado para Arch Linux (PKGBUILD + perfil archiso).

```
nexora/
  cli.py             CLI principal (nexora), incluye subcomando nke
  watchdog.py        Supervisión ligera (pasada única, diagnóstico, bucle acotado)
  core/
    config.py        Configuración por capas (defaults + usuario) y validación
    permissions.py   Permisos por herramienta (concesión explícita)
    profiles.py      Perfiles de hardware (CPU/RAM/GPU/almacenamiento)
    registry.py      Registro de modos y creación de agentes
    vault.py         Bóveda (memoria o keyring del SO)
    ai_engine.py     Motor IA: local_mock, ollama, llamacpp, localai
    resources.py     Inventario del sistema, niveles y perfiles híbridos
    coordinator.py   Coordinador de agentes (permisos, aprobación, historial)
  nke/               Nexora Kernel Engine (ver docs/NKE.md)
    capabilities.py  Detección de capacidades del kernel real
    monitor.py       Monitor con sondeo adaptativo
    analyzer.py      Análisis de hallazgos
    policy.py        Catálogo de acciones y categorías A/B/C
    safety.py        Safety Controller (validación, rollback)
    engine.py        Ciclo completo con cooldowns y rollback automático
    history.py       Historial de decisiones
    kernel_extension.py  Kernel/Module/Hardware managers y ExtensionAPI
    cli.py           Comando nexora-nke
  agents/
    base.py          Agente base: memoria aislada por modo
    meteorology.py   Modo Meteorology
    security.py      Modo Security: auditoría defensiva de solo lectura
  connectors/        account_hub, browser (sin extracción de credenciales)
  diagnostics/       health.py
  ui/                dashboard.py (texto, con panel Kernel Engine)
packaging/
  arch/PKGBUILD      Paquete nexora-os (incluye nexora-nke.service)
  archiso/           Perfil live (profiledef.sh, packages.x86_64, pacman.conf, airootfs)
  systemd/           Unidades del watchdog y de NKE
scripts/build-iso.sh Build del wheel + tests + ISO con verificación
```

## Principios

1. Memoria aislada por agente: lo que un modo recuerda no es visible para otro (verificado por test).
2. Permisos mínimos: operaciones sensibles exigen concesión explícita; el agente Security es de solo lectura salvo informe explícito.
3. Sin secretos en texto plano: bóveda en memoria o keyring del SO.
4. Motor IA: solo loopback por defecto; el modo simulado se marca siempre con `simulated: true`; nunca descarga modelos.
5. Watchdog conservador: observa y recomienda; solo ejecuta la recuperación registrada por el componente; nunca modifica configuración ni políticas.
6. Ligero: sin daemons residentes por defecto; las unidades systemd son opcionales y con límites de recursos.
7. NKE nunca toca el kernel: actúa solo sobre interfaces estándar, clasifica cada acción en A (automática reversible), B (supervisada) o C (protegida, nunca ejecutada), y revierte automáticamente si un ajuste degrada el sistema.

## Nexora Kernel Engine

NKE es un subsistema transversal (no un daemon obligatorio) que observa el estado del sistema y aplica optimizaciones seguras. Detalle completo en `docs/NKE.md`. Decisiones clave:

- Todo pasa por el Safety Controller: los agentes no acceden a `/proc` ni `/sys` directamente, usan la ExtensionAPI de consultas cerradas.
- La categoría C (carga de módulos, parámetros de arranque, sysctls críticos) nunca se ejecuta desde NKE; se lista como propuesta con `executed_by_nke: false`.
- Con la unidad systemd en DynamicUser, NKE funciona en modo observación y propuestas; los writes privilegiados quedan denegados y registrados, que es el comportamiento seguro previsto.

## Interfaz gráfica (futura)

Pendiente una GUI completa. El dashboard de texto ya expone el panel Kernel Engine; la intención es una capa gráfica sobre el mismo plano de control (los agentes, la CLI y NKE exponen las mismas operaciones), sin duplicar lógica.

## Comunicación entre agentes

Los agentes no se llaman entre sí directamente: comparten estado a través del registro y contratos explícitos (resultados de `query`, informes de auditoría, mensajes del coordinador). La memoria es privada por modo.
