# Arquitectura — NexoraOS

## Visión general

Plano de control en Python (paquete `nexora`) con agentes por modo, bóveda de secretos, permisos por herramienta, watchdog ligero y empaquetado para Arch Linux (PKGBUILD + perfil archiso).

```
nexora/
  cli.py             CLI principal (nexora)
  watchdog.py        Supervisión ligera (pasada única, diagnóstico, bucle acotado)
  core/
    config.py        Configuración por capas (defaults + usuario) y validación
    permissions.py   Permisos por herramienta (concesión explícita)
    profiles.py      Perfiles de hardware (CPU/RAM/GPU/almacenamiento)
    registry.py      Registro de modos y creación de agentes
    vault.py         Bóveda (memoria o keyring del SO)
    ai_engine.py     Motor IA: local_mock, ollama, llamacpp, localai
  agents/
    base.py          Agente base: memoria aislada por modo
    meteorology.py   Modo Meteorology
    security.py      Modo Security: auditoría defensiva de solo lectura
  connectors/        account_hub, browser (sin extracción de credenciales)
  diagnostics/       health.py
  ui/                dashboard.py (texto)
packaging/
  arch/PKGBUILD      Paquete nexora-os
  archiso/           Perfil live (profiledef.sh, packages.x86_64, pacman.conf, airootfs)
  systemd/           Unidades del watchdog (sistema y usuario)
scripts/build-iso.sh Build del wheel + tests + ISO con verificación
```

## Principios

1. Memoria aislada por agente: lo que un modo recuerda no es visible para otro (verificado por test).
2. Permisos mínimos: operaciones sensibles exigen concesión explícita; el agente Security es de solo lectura salvo informe explícito.
3. Sin secretos en texto plano: bóveda en memoria o keyring del SO.
4. Motor IA: solo loopback por defecto; el modo simulado se marca siempre con `simulated: true`; nunca descarga modelos.
5. Watchdog conservador: observa y recomienda; solo ejecuta la recuperación registrada por el componente; nunca modifica configuración ni políticas.
6. Ligero: sin daemons residentes por defecto; la unidad systemd del watchdog es opcional y con límites de recursos.

## Interfaz gráfica (futura)

Pendiente. La intención es una capa sobre el mismo plano de control (los agentes y la CLI exponen las mismas operaciones), sin duplicar lógica. No existe implementación: no se debe asumir que haya GUI.

## Comunicación entre agentes

Los agentes no se llaman entre sí directamente: comparten estado a través del registro y contratos explícitos (resultados de `query`, informes de auditoría). La memoria es privada por modo.
