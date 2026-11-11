# Informe de calidad (QA) — NKE y Fases 1-2

Fecha: 2026-11-11. Alcance: Nexora Kernel Engine (NKE) sobre el estado de las Fases 1-2 (commits 7792bad, 75fcb11, 7741cbf).

## 1. Qué se implementó en NKE

- Motor completo en espacio de usuario: detección de capacidades, monitor adaptativo, analizador, motor de políticas con categorías A/B/C, Safety Controller con rollback, historial, ciclo del motor con cooldowns y CLI.
- Integración: subcomando `nexora nke`, comando `nexora-nke`, panel Kernel Engine en el dashboard, componente `nke` en el watchdog, unidad systemd endurecida, instalación por PKGBUILD.
- Documentación: `docs/NKE.md`.

## 2. Pruebas ejecutadas y resultados exactos

| Prueba | Dónde | Resultado |
| --- | --- | --- |
| Tests unitarios Python 3.10 y 3.12 (run de 7792bad) | GitHub Actions | NO VERIFICADO: los runs quedaron en cola (runners del plan gratuito saturados); la API de GitHub alcanzó su límite de tasa |
| Tests de NKE (test_nke.py, test_watchdog.py actualizado) | GitHub Actions | NO VERIFICADO aún: se pushean en este commit; el resultado real se consultará en Actions |
| Tests locales | Este entorno | NO ejecutados: no hay intérprete Python disponible en el sandbox |
| Aplicación real de cgroups/renice en vivo | Ninguno | NO probada: probada con executor simulado; requiere host real con permisos |
| Arranque de la ISO | Ninguno | NO verificado: requiere QEMU o hardware |
| Consumo de NKE en vivo | Ninguno | NO medido en host real; el diseño limita la huella (sondeo adaptativo, MemoryMax=80M, CPUQuota=2%) |

## 3. Bugs encontrados y corregidos en este ciclo

1. El Safety Controller derivaba mal las rutas de cpufreq desde el punto de montaje de cgroups: corregido con parámetro `sys_root` explícito.
2. El umbral del test de rollback por degradación era incorrecto (contaba un ciclo de menos): corregido a dos ciclos sin mejora.
3. El test `test_watchdog_from_config` no contemplaba el nuevo componente `nke`: actualizado.

## 4. Problemas de UX/UI

- El panel Kernel Engine del dashboard es de texto y muestra estado y capacidades; las propuestas B/C aún no tienen flujo de aprobación interactivo (se listan con su comando de revisión).
- Sin GUI: documentado como pendiente.

## 5. Seguridad

- NKE nunca ejecuta la categoría C; las propuestas C se marcan con `executed_by_nke: false`.
- Los agentes no acceden a `/proc` ni `/sys`: solo ExtensionAPI de consultas cerradas.
- La unidad nexora-nke.service usa DynamicUser y endurecimiento completo; en ese modo los writes privilegiados se deniegan y registran (comportamiento previsto y documentado).
- Sin secretos ni datos personales en el código (gitleaks en CI).

## 6. Estado de watchdogs y daemons

- Watchdog del core: 4 componentes (config, agent_isolation, vault, nke); diagnóstico sin efectos; anti-bucle en modo bucle.
- NKE: no es daemon obligatorio; unidad systemd opcional con límites estrictos y protección anti-bucle propia (exit 3 tras errores consecutivos).

## 7. Limitaciones y pendientes

- eBPF: la detección de capacidad existe; los programas eBPF concretos son una fase posterior (documentado en docs/NKE.md).
- GPU/VRAM y batería: el monitor de NKE aún no las lee (resources.py del core sí).
- CI: pendiente de confirmar runs verdes; el tag v0.4.0 no se crea hasta tener CI verde.
- Sin pruebas contra Ollama/llama.cpp reales (validado con transporte falso que replica sus APIs).
