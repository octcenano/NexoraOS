# Informe de calidad (QA) — Beta 0.4.0 de NexoraOS

Fecha: 2026-11-11. Alcance: cierre de beta con Nexora Desktop, modos oficiales, NKE, CI verde y procesos de seguridad y release.

## 1. Pruebas ejecutadas y resultados exactos (CI, GitHub Actions)

| Prueba | Dónde | Resultado |
| --- | --- | --- |
| Tests unitarios (248+ tests, Python 3.10 y 3.12) | Runs 40 y 41 (CI verde) | VERDE |
| Smoke test CLI (nexora --help, nexora health, nexora-watchdog --diagnose) | Runs 40 y 41 | VERDE |
| Lint (ShellCheck, bash -n, gitleaks 8.21.2) | Runs 40 y 41 | VERDE |
| Construcción y validación del wheel | Runs 40 y 41 | VERDE |
| Construcción de la ISO (mkarchiso, contenedor archlinux:base privilegiado) | Runs 40 y 41 (8-9 min) | VERDE: ISO construida |
| Workflow de seguridad (bandit, pip-audit, gitleaks sobre historial) | Nuevo workflow | Pendiente de primer run; se ejecuta en el próximo push y semanalmente |
| Workflow de release (tag v* → wheel + ISO + release borrador) | Nuevo workflow | Pendiente de primer tag; no se crea el tag hasta confirmar verde |
| Vista GTK3 de Nexora Desktop | Ninguno | NO ejecutada: sin PyGObject ni sesión gráfica; probada la ausencia controlada |
| Arranque de la ISO | Ninguno | NO verificado: requiere QEMU o hardware |
| Consumo en reposo del escritorio | Ninguno | NO medido: no se publican cifras sin medición reproducible |
| Pruebas contra Ollama/llama.cpp reales | Ninguno | NO: validado con transporte falso que replica sus APIs |

## 2. Bugs encontrados y corregidos durante el desarrollo de la beta (causa raíz)

1. Cooldown del NKEngine a t=0 bloqueaba toda acción automática al arrancar.
2. defaults.json empaquetado desactualizado (0.2.0-beta): nexora health fallaba en CI.
3. Muestreo degradado de PSI en test_nke escribía después de leer.
4. profiledef.sh con bloque INI inválido: sustituido por buildmodes=('iso').
5. Validación de mkarchiso: uefi.systemd no existe (uefi.systemd-boot); faltaban syslinux, syslinux.cfg, efiboot/loader/entries.
6. mkarchiso no puede montar proc sin contenedor privilegiado: options: --privileged.
7. pacman abortaba por *.db.sig 404: SigLevel = Required DatabaseOptional (estándar releng).
8. Tests desalineados con la API real (intensity_policy devuelve dict; launch rechaza con "rejected"): tests corregidos.
9. Diagnóstico de CI ilegible: los tres jobs publican issues al fallar (iso-build vía curl).

## 3. Estado por área (beta 0.4.0)

- Core, Coordinator, modos oficiales con intensidades reales: funcionales y probados en CI.
- NKE: motor, categorías A/B/C, rollback, API de aprobación: funcionales; sin verificación en host real.
- Watchdog y daemons systemd endurecidos: funcionales; sin verificación en host real.
- Nexora Desktop: Shell, Dashboard, Mode Center, NKE Control, Hub y System Center completos con datos reales y estados explícitos; System Center incluye usuarios (solo lectura), actualizaciones pendientes (pacman -Qu) y actualización del sistema vía pkexec con lista cerrada.
- Vista GTK3: implementada, no ejecutada visualmente.
- Seguridad: sin root, listas blancas, auditoría defensiva de solo lectura, bandit/pip-audit/gitleaks en CI, release solo manual.

## 4. Pendientes declaradas (fuera de la beta o post-beta)

- Arranque de la ISO en QEMU o hardware (requiere entorno con KVM o máquina física).
- Verificación del NKE, watchdog y unidades systemd en host real.
- eBPF: programas concretos (hoy: detección y degradación declarada).
- Edición de cuentas de usuario y gestión de servicios con polkit (fuera de la beta).
- Pruebas contra Ollama/llama.cpp reales.
- ZIP obsoleto NEXORA_OS_BETA_0.2.zip en la raíz del repositorio: el conector no permite borrar archivos; borrado manual pendiente.
- Consumo en reposo: sin medir; no se publican cifras.
- Primer tag v0.4.0-beta una vez confirmado el workflow de seguridad en verde.
