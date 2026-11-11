# Modos de NEXORA OS

NEXORA OS tiene cinco modos oficiales. Son perfiles combinables y adaptativos, no cinco distribuciones distintas. Cada modo dispone de cuatro niveles de intensidad: 1, 2, 3 y full.

| Modo | Estado | Herramientas declaradas | Intensidad por defecto |
|---|---|---|---|
| Gaming | stub (solo registrado) | `local_ai`, `performance_profile` | 2 |
| Hacking | stub (solo registrado) | `local_ai`, `defensive_audit_readonly`, `lab_network_isolated` | 1 |
| Office | stub (solo registrado) | `local_ai` | 1 |
| Stealth | stub (solo registrado) | `local_ai` | 1 |
| Forge | stub (solo registrado) | `local_ai` | 2 |

Aclaraciones de alcance (decisiones de producto):

- **Creator NO es un modo oficial.**
- **Meteorology** es un agente especializado (comando `nexora weather`), no un modo principal.
- **Security** es una funcionalidad transversal y un agente defensivo (comando `nexora audit`, auditoría de solo lectura), no un modo principal.
- **Forge** corresponde al entorno de desarrollo.

## Intensidades

Cada nivel es una política real del núcleo adaptativo (`nexora/core/resources.py`: level1, level2, level3, full) con agentes concurrentes, RAM máxima para modelos, peso de CPU y reglas de ajuste agresivo. La intensidad es una declaración de política que consume el reparto de recursos (`build_allocation`); no modifica el sistema directamente.

- **1**: consumo mínimo, un agente, modelos pequeños.
- **2**: equilibrado, dos agentes, modelos medianos.
- **3**: rendimiento elevado, cuatro agentes, modelos grandes.
- **full**: prioridad total para el modo; el ajuste agresivo exige compatibilidad comprobada y aprobación explícita del usuario.

Uso:

```
nexora mode gaming                 # muestra la política efectiva
nexora mode gaming --intensity 3   # fija la intensidad
nexora modes                       # lista los modos oficiales y los agentes especializados
```

El nivel full nunca activa capacidades ofensivas ni desactiva protecciones de seguridad globales. En el modo Hacking solo se contemplan ciberseguridad autorizada, auditoría defensiva y laboratorios propios; las acciones sensibles exigen aprobación humana.

## Estado honesto

Los cinco modos están registrados con memoria privada aislada, política de herramientas y niveles de intensidad funcionales. Sus agentes son de propósito general (BaseAgent): las capacidades específicas de cada modo (ajustes de rendimiento de Gaming, laboratorios de Hacking, etc.) están pendientes de implementación y se declaran como stub. El estado real de cada modo se consulta con `nexora modes`.
