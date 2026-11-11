# Informe de calidad (QA) — Nexora Desktop, modos oficiales, NKE y CI

Fecha: 2026-11-11. Alcance: estado tras Nexora Desktop, los cinco modos oficiales, el NKE y la corrección de la CI (HEAD faa9012).

## 1. Pruebas ejecutadas y resultados exactos (CI, GitHub Actions)

| Prueba | Dónde | Resultado |
| --- | --- | --- |
| Tests unitarios (248 tests, Python 3.10 y 3.12) | GitHub Actions, run #34 en adelante (commit 48c2de4) | VERDE: el job tests pasó en todos los runs desde la corrección de los dos tests (no se publicó ningún issue de tests desde el run 34) |
| Smoke test CLI (nexora --help, nexora health, nexora-watchdog --diagnose) | GitHub Actions | VERDE desde el run 34 |
| Lint (ShellCheck, bash -n, gitleaks 8.21.2) | GitHub Actions | VERDE (runs 33-39) |
| Construcción y validación del wheel | GitHub Actions | VERDE (sin issue de package desde que existe diagnóstico) |
| Construcción de la ISO | GitHub Actions, runs 35-39 | PROGRESO: validación del perfil superada (run 38), montaje del chroot superado con contenedor privilegiado, sincronización de pacman corregida (SigLevel); el último run (SigLevel) seguía en cola o compilando al cerrar este informe |
| Tests locales | Este entorno | NO ejecutados: no hay intérprete Python en el sandbox; toda la validación se hace en CI |
| Vista GTK3 de Nexora Desktop | Ninguno | NO ejecutada: sin PyGObject ni sesión gráfica; probada la ausencia controlada (error claro) |
| Arranque de la ISO | Ninguno | NO verificado: requiere QEMU o hardware |
| Consumo en reposo del escritorio | Ninguno | NO medido: no se publican cifras sin medición reproducible |

## 2. Bugs encontrados y corregidos (este ciclo, con causa raíz)

1. Cooldown del NKEngine a t=0: `now - 0.0 < 300` bloqueaba toda acción automática al arrancar. Corregido: solo aplica cooldown si hay acción previa registrada.
2. `defaults.json` empaquetado desactualizado (0.2.0-beta frente a 0.4.0-beta): `nexora health` fallaba en el smoke test de CI.
3. `test_degradacion_provoca_rollback`: el muestreo reescribía PSI después de leer; corregido para escribir antes de leer.
4. `service_state` y sockets: aceptar tcp y tcp6 (el mock de builtins.open hacía que ambas familias leyeran el mismo contenido).
5. `profiledef.sh`: bloque INI inválido `[build] options=()` sustituido por `buildmodes=('iso')`.
6. Validación de mkarchiso (issue 35): `uefi.systemd` no es un modo válido (es `uefi.systemd-boot`); faltaba el paquete syslinux, el directorio syslinux/ y efiboot/loader/entries. Corregido con profiledef, syslinux.cfg, loader.conf y entrada UEFI.
7. mkarchiso no puede montar proc en un contenedor sin privilegios (issue 38): `container: options: --privileged` en CI.
8. pacman abortaba por *.db.sig 404 (issue 39): `SigLevel = Required DatabaseOptional` (estándar releng) en el pacman.conf del perfil.
9. Tests desalineados con la API real: `intensity_policy()` devuelve un dict (no un objeto con .policy) y `SystemCenter.launch()` rechaza con "rejected" los comandos fuera de la lista blanca (no "unavailable"). Tests corregidos.
10. Diagnóstico de CI ilegible (logs 403): los tres jobs (tests, package, iso-build) publican ahora su diagnóstico en un issue al fallar; iso-build lo hace vía API con curl porque gh no existe en el contenedor Arch.

## 3. Estado por área

- Nexora Desktop: modelos completos con datos reales y estados explícitos; vista GTK3 implementada, no ejecutada visualmente.
- Modos oficiales: cinco modos con intensidades 1/2/3/full respaldadas por LevelPolicy reales; agentes específicos de cada modo pendientes (estado declarado: stub).
- NKE: motor, categorías A/B/C, rollback, API de aprobación; sin verificación en host real.
- Watchdog: 4 componentes, diagnóstico sin efectos, anti-bucle.
- Seguridad: auditoría defensiva de solo lectura; interfaz sin root; lista blanca de comandos; sin ejecución de comandos generados por modelos.

## 4. Limitaciones y pendientes

- Confirmar el run de CI con la construcción completa de la ISO; el tag v0.4.0 no se crea hasta tener CI verde.
- eBPF: detección y degradación declarada; programas eBPF concretos pendientes.
- cgroups/renice aplicados en vivo: requiere host real.
- Pruebas contra Ollama/llama.cpp reales: validado con transporte falso que replica sus APIs.
- ZIP obsoleto NEXORA_OS_BETA_0.2.zip en la raíz del repositorio: el conector no permite borrar archivos; borrado manual pendiente.
- Issues de diagnóstico de CI (1-39) abiertos: se cerrarán cuando la CI esté completamente verde.
