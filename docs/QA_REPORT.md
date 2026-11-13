# Informe de calidad (QA) — Beta 0.4.0 de NexoraOS

Fecha: 2026-11-13. Alcance: cierre de beta con Nexora Desktop completo, modos oficiales, NKE, CI verde, workflows de seguridad y release, y limpieza del repositorio.

## 1. Pruebas ejecutadas y resultados exactos (CI, GitHub Actions)

| Prueba | Dónde | Resultado |
| --- | --- | --- |
| Tests unitarios (257, Python 3.10 y 3.12) | Run 53 de CI (commit 432d307) | VERDE |
| Smoke test CLI | Run 53 | VERDE |
| Lint (ShellCheck, bash -n, gitleaks 8.21.2) | Run 53 | VERDE |
| Wheel (construcción y validación) | Run 53 | VERDE |
| ISO (mkarchiso, contenedor privilegiado) | Run 53 | VERDE: ISO construida |
| Runs de CI también verdes: 40, 41, 42, 51, 53 | Commits faa9012, 3d0184c, 01a3dcb, 8b82e7d, 432d307 | VERDE |
| Bandit (análisis estático) | Workflow Seguridad, runs 10, 11 y 12 | VERDE (sin hallazgos; nosec B310 justificado con validación de esquema https) |
| pip-audit (dependencias) | Workflow Seguridad, runs 10, 11 y 12 | VERDE (paquete local excluido del freeze; --no-deps con --disable-pip) |
| Gitleaks sobre historial completo | Workflow Seguridad, runs 10, 11 y 12 | VERDE (sin hallazgos) |
| Runs de CI en cola al cerrar este informe | Runs 54, 55, 56 (commits 8013f8e, 62a750b, ec63ccf) | EN COLA por saturación de runners del plan gratuito; la diferencia con 432d307 es solo documentación y el borrado del ZIP, sin código ejecutable |
| Workflow de release (tag v*) | Sin tag aún | NO EJECUTADO: el conector no permite crear tags; creación manual pendiente (ver sección 5) |
| Vista GTK3 | Ninguno | NO ejecutada: sin PyGObject ni sesión gráfica; ausencia controlada probada |
| Arranque de la ISO | Ninguno | NO verificado: requiere QEMU o hardware |
| Consumo en reposo | Ninguno | NO medido: no se publican cifras sin medición |

## 2. Limpieza del repositorio (2026-11-13)

- Eliminado el ZIP obsoleto NEXORA_OS_BETA_0.2.zip de la raíz (commit ec63ccf): los artefactos reales se generan en CI y en releases.
- Sin issues abiertos; todos los issues de diagnóstico (1 a 69) cerrados como completed.
- Estructura verificada: docs (10 documentos), scripts (build-iso.sh), packaging (arch, archiso, systemd, xfce), config, tests.

## 3. Bugs corregidos en el ciclo de cierre (causa raíz)

1. Validación de mkarchiso: uefi.systemd inválido, syslinux y efiboot/loader/entries ausentes.
2. Contenedor sin privilegios: mkarchiso no podía montar proc (options: --privileged).
3. pacman abortaba por *.db.sig 404: SigLevel Required DatabaseOptional (estándar releng).
4. Tests desalineados con la API real (intensity_policy dict; launch "rejected"; pacman inexistente "unavailable").
5. Doble codificación UTF-8 heredada en tests y datos de meteorology (España, Código WMO): corregido el motor en e24b5c0 y la expectativa del test en 8643187; los runs 43 a 49 fallaron por esta causa y el run 53 confirma la suite completa en verde.
6. Bandit B310 en urlopen: validación de esquema https + nosec justificado en la línea de la llamada.
7. pip-audit: el paquete local (nexora-os @ file://) no es auditable en PyPI; se excluye del freeze y se audita el resto con --no-deps.

## 4. Estado por área (beta 0.4.0)

- Core, Coordinator, cinco modos oficiales con intensidades reales: funcionales, probados en CI (257 tests).
- NKE: motor A/B/C, rollback, API de aprobación: funcional; verificación en host real pendiente.
- Watchdog y unidades systemd endurecidas: funcionales; verificación en host real pendiente.
- Nexora Desktop: Shell, Dashboard, Mode Center, NKE Control, Hub y System Center completos con datos reales y estados explícitos. System Center incluye usuarios (solo lectura), actualizaciones pendientes (pacman -Qu) y actualización del sistema vía pkexec con lista cerrada de argv.
- Vista GTK3: implementada, no ejecutada visualmente.
- Seguridad: sin root, listas blancas, auditoría defensiva de solo lectura, bandit/pip-audit/gitleaks en verde, release solo manual (borrador).

## 5. Pendientes declaradas

- Crear el tag v0.4.0-beta manualmente (el conector de GitHub no permite crear tags): git tag v0.4.0-beta && git push origin v0.4.0-beta. Esto dispara release.yml (wheel + ISO + release borrador).
- Confirmar los runs 54 a 56 de CI cuando la cola lo permita (solo cambios de documentación y borrado del ZIP respecto al run 53 verde).
- Arranque de la ISO en QEMU o hardware.
- Verificación de NKE, watchdog y systemd en host real.
- Programas eBPF concretos (hoy: detección y degradación declarada).
- Edición de cuentas y gestión de servicios con polkit (fuera de la beta).
- Pruebas contra Ollama/llama.cpp reales.
- Vista GTK3 ejecutada en un entorno gráfico real.
