# Informe de calidad (QA) — Beta 0.4.0 de NexoraOS

Fecha: 2026-11-12. Alcance: cierre de beta con Nexora Desktop completo, modos oficiales, NKE, CI verde, workflows de seguridad y release.

## 1. Pruebas ejecutadas y resultados exactos (CI, GitHub Actions)

| Prueba | Dónde | Resultado |
| --- | --- | --- |
| Tests unitarios (248, Python 3.10 y 3.12) | Runs 40 y 41 de CI | VERDE (última revisión confirmada: commit 3d0184c) |
| Smoke test CLI | Runs 40 y 41 | VERDE |
| Lint (ShellCheck, bash -n, gitleaks 8.21.2) | Runs 40 y 41 | VERDE |
| Wheel (construcción y validación) | Runs 40 y 41 | VERDE |
| ISO (mkarchiso, contenedor privilegiado) | Runs 40 y 41 (8-9 min) | VERDE: ISO construida |
| Tests de System Center ampliados (257) y fix de meteorología | Commits posteriores a 3d0184c | PUSHEADOS; run en cola por saturación de runners del plan gratuito |
| Bandit (análisis estático) | Workflow Seguridad, runs 8 y 9 | VERDE (nosec B310 justificado con validación de esquema https) |
| pip-audit (dependencias) | Workflow Seguridad, run 10 | EN COLA; causas de los fallos 3-9 corregidas (paquete local excluido del freeze, --no-deps con --disable-pip) |
| Gitleaks sobre historial completo | Workflow Seguridad | VERDE (sin hallazgos) |
| Workflow de release (tag v*) | Sin tag aún | NO EJECUTADO: el tag se crea cuando la cola lo permita confirmar todo en verde |
| Vista GTK3 | Ninguno | NO ejecutada: sin PyGObject ni sesión gráfica; ausencia controlada probada |
| Arranque de la ISO | Ninguno | NO verificado: requiere QEMU o hardware |
| Consumo en reposo | Ninguno | NO medido: no se publican cifras sin medición |

## 2. Bugs corregidos en el ciclo de cierre (causa raíz)

1. Validación de mkarchiso: uefi.systemd inválido, syslinux y efiboot/loader/entries ausentes.
2. Contenedor sin privilegios: mkarchiso no podía montar proc (options: --privileged).
3. pacman abortaba por *.db.sig 404: SigLevel Required DatabaseOptional (estándar releng).
4. Tests desalineados con la API real (intensity_policy dict; launch "rejected"; pacman inexistente "unavailable").
5. Doble codificación UTF-8 heredada en tests y datos de meteorology (España, Código WMO): corregida a UTF-8 correcto.
6. Bandit B310 en urlopen: validación de esquema https + nosec justificado en la línea de la llamada.
7. pip-audit: el paquete local (nexora-os @ file://) no es auditable en PyPI; se excluye del freeze y se audita el resto con --no-deps.

## 3. Estado por área (beta 0.4.0)

- Core, Coordinator, cinco modos oficiales con intensidades reales: funcionales, probados en CI.
- NKE: motor A/B/C, rollback, API de aprobación: funcional; verificación en host real pendiente.
- Watchdog y unidades systemd endurecidas: funcionales; verificación en host real pendiente.
- Nexora Desktop: Shell, Dashboard, Mode Center, NKE Control, Hub y System Center completos con datos reales y estados explícitos. System Center incluye usuarios (solo lectura), actualizaciones pendientes (pacman -Qu) y actualización del sistema vía pkexec con lista cerrada de argv.
- Vista GTK3: implementada, no ejecutada visualmente.
- Seguridad: sin root, listas blancas, auditoría defensiva de solo lectura, bandit/pip-audit/gitleaks en CI, release solo manual (borrador).

## 4. Pendientes declaradas

- Confirmar en CI los commits finales (cola de runners saturada al cerrar este informe).
- Arranque de la ISO en QEMU o hardware.
- Verificación de NKE, watchdog y systemd en host real.
- Programas eBPF concretos (hoy: detección y degradación declarada).
- Edición de cuentas y gestión de servicios con polkit (fuera de la beta).
- Pruebas contra Ollama/llama.cpp reales.
- ZIP obsoleto NEXORA_OS_BETA_0.2.zip en la raíz: borrado manual pendiente (el conector no permite borrar).
- Primer tag v0.4.0-beta cuando la CI confirme verde completo.
