# Nexora Kernel Engine (NKE)

## Qué es

NKE es un motor de optimización en espacio de usuario que opera sobre las
interfaces estándar del kernel Linux: `/proc`, `/sys`, PSI (Pressure Stall
Information), cgroups v2 y systemd. No modifica el kernel, no carga módulos y
no requiere parches. Todo el motor vive en `nexora/nke/`.

## Componentes

| Componente | Archivo | Función |
|---|---|---|
| Capabilities | `capabilities.py` | Detecta qué soporta el kernel real (PSI, cgroups v2, eBPF, cpufreq, swap, Secure Boot) |
| Monitor | `monitor.py` | Lee meminfo, loadavg, PSI y procesos top; sondeo adaptativo (2 s a 60 s) |
| Analyzer | `analyzer.py` | Hallazgos por umbrales (presión de memoria/CPU/IO, swap thrashing, poca RAM) |
| Policy Engine | `policy.py` | Convierte hallazgos en acciones clasificadas por categoría |
| Safety Controller | `safety.py` | Valida y aplica acciones; rollback automático |
| History | `history.py` | Registro acotado de decisiones y rollbacks |
| Engine | `engine.py` | Ciclo completo con cooldowns y detección de degradación |
| Kernel Extension | `kernel_extension.py` | Estado del kernel, módulos cargados (solo lectura), hardware, propuestas |

## Tres categorías de actuación

- Categoría A (automática): ajustes reversibles y de bajo riesgo dentro de
  políticas autorizadas (renice, límites de cgroups propios, perfiles cpufreq).
  Se aplican solas, con cooldown por objetivo (300 s) y rollback si degradan.
- Categoría B (supervisada): se preparan y se listan como propuestas; requieren
  aprobación humana explícita antes de ejecutarse.
- Categoría C (protegida): nunca se ejecutan desde NKE. Se listan como
  propuestas informativas con `executed_by_nke: false` (carga de módulos,
  parámetros de arranque, sysctls críticos).

## Capacidades detectadas

`detect_capabilities()` comprueba en el sistema real:

- PSI: existencia de `/proc/pressure/{cpu,memory,io}`.
- cgroups v2: presencia y punto de montaje de `/sys/fs/cgroup/cgroup.controllers`.
- eBPF: bpffs montado y valor de `kernel.unprivileged_bpf_disabled`.
- cpufreq: `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`.
- swap: TotalSwap en meminfo.
- Secure Boot: lectura de efivars (mejor esfuerzo).

Si una capacidad no existe, el Policy Engine no propone acciones que la
requieran. No se presupone soporte.

## Huella y anti-bucles

- Sondeo adaptativo: intervalo mínimo 2 s, se duplica hasta 60 s en reposo y
  vuelve al mínimo cuando hay presión.
- Máximo 3 acciones automáticas por ciclo; cooldown de 300 s por objetivo.
- Si tras aplicar una acción el hallazgo no mejora en 2 ciclos, rollback
  automático del ajuste y registro en el historial.
- Unidad systemd `nexora-nke.service` con `MemoryMax=80M`, `CPUQuota=2%`,
  `DynamicUser` y endurecimiento completo. Con DynamicUser NKE funciona en modo
  observación y propuestas; los writes a cgroups quedarán denegados y
  registrados, que es el comportamiento seguro previsto.

## Uso

```bash
nexora nke status      # capacidades y estado del motor (solo lectura)
nexora nke diagnose    # ejecuta un ciclo y lista propuestas B/C
nexora nke history     # eventos y rollbacks recientes
nexora-nke --once      # un ciclo (JSON opcional con --json)
nexora-nke --loop 30   # bucle con protección anti-bucle (exit 3 tras errores)
```

## Integración

- Watchdog del core: componente `nke` que verifica que las capacidades se leen.
- Dashboard: panel `Kernel Engine` con release, capacidades y estado.
- Agentes: no acceden a `/proc` ni `/sys`; usan la ExtensionAPI de consultas
  cerradas (`nexora.nke.kernel_extension.ExtensionAPI`).

## Pendiente documentado

- Aplicación real de límites de cgroups en vivo: implementada y probada con
  executor simulado; pendiente de validación en hardware real con permisos.
- eBPF: la detección existe; los programas eBPF concretos son una fase
  posterior y se documentan como pendientes.
- GPU/VRAM y batería: lecturas no implementadas todavía en el monitor.
