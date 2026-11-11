# Roadmap — NexoraOS

## Fase 1 — Estabilización (2026-11-11, hecha salvo verificación de CI)

- Corregido el test de cooldown del watchdog (regresión introducida en 0.4).
- CI sin ocultación de errores (`|| true` y `continue-on-error` eliminados) y con diagnóstico visible (anotaciones).
- Job de ISO real en contenedor arch:base (pendiente de primera ejecución completa).
- Pendiente: confirmar CI verde en los runs de los commits 7792bad y posteriores.

## Fase 2 — Arquitectura (2026-11-11, base implementada)

- `nexora/core/resources.py`: inventario real, niveles level1/level2/level3/full como políticas verificables, perfiles híbridos con modo primario y planes reversibles. (Implementado y probado; sin aplicación al sistema en vivo todavía.)
- `nexora/core/coordinator.py`: coordinador con permisos, aprobación e historial. (Implementado y probado.)
- Pendiente: aplicar planes reales (CPU governor, cgroups por agente) con aprobación explícita; integración del coordinador con la CLI y el dashboard.

## Fase 3 — Integración de modos (pendiente)

- Gaming, Office/Study, Stealth, Forge y catálogo Hacking con herramientas declaradas y aprobación humana para operaciones sensibles. Sin capacidades ofensivas autónomas.
- Model Manager sobre ai_engine (requisitos RAM/VRAM por modelo, selección por tarea).

## Fase 4 — Interfaz gráfica (pendiente)

- Dashboard, centro de agentes, centro de perfiles y centro de IA sobre el modelo de estado existente (render_layout). Sin implementación todavía.

## Fase 5 — Distribución (pendiente)

- ISO reproducible verificada en CI, arranque probado en QEMU, instalador guiado, configuración regional española.

## Notas de reorganización

- La Fase 2 se adelantó respecto al plan original porque el coordinador y el gestor de recursos son prerrequisito de los modos (Fase 3) y de la GUI (Fase 4): sin reparto de recursos y sin política de tareas, los modos serían etiquetas.
