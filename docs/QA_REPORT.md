# Informe de calidad (QA) — Beta 0.4

Fecha: 2026-11-11. Alcance: cambios de la Beta 0.4 sobre la Beta 0.3 (commit 7ec4f0b).

## 1. Bugs encontrados

1. `scripts/build-iso.sh` podía reutilizar una ISO antigua de `out/` y validar un artefacto anterior; también copiaba todos los wheels presentes en `dist/`.
2. El watchdog no tenía modo diagnóstico ni historial de incidencias; un error interno en modo bucle podía provocar un bucle de fallos silencioso.
3. `list_models()` del motor IA no existía con semántica real por backend; no había forma de comprobar si un modelo está disponible.
4. La auditoría Security solo contaba sockets en escucha (sin detalle de puertos) y no evaluaba la antigüedad de las actualizaciones.
5. Las unidades systemd del watchdog no limitaban recursos y usaban una acción flotante de shellcheck en CI (riesgo de rotura repentina).

## 2. Bugs corregidos

Todos los anteriores: ver `CHANGELOG.md` 0.4.0-beta. Cada corrección tiene tests asociados.

## 3. Bugs pendientes

- Ninguno conocido abierto en el código Python tras los tests; los riesgos reales están en la sección de limitaciones.

## 4. Problemas de UX/UI

- La interfaz sigue siendo un dashboard de texto y una CLI: no hay estados de carga visuales ni interfaz gráfica. Documentado como pendiente para 0.5.
- Los mensajes de error del motor IA y del watchdog ahora son accionables (sugieren comando o causa), pero la CLI no agrupa errores de múltiples comandos.

## 5. Problemas de seguridad

- Corregido: gitleaks fijo, informe Security con permisos 600 y escritura única, endpoints remotos rechazados por defecto.
- Riesgo residual: el modo `local_mock` podría confundirse con una conexión real si se ignora el campo `simulated`; todas las respuestas lo marcan.

## 6. Estado de watchdogs y daemons

- Watchdog: implementado (pasada única, `--diagnose`, bucle con límite de errores consecutivos). Unidades systemd de sistema y usuario con límites (MemoryMax=150M, CPUQuota=5%) y endurecimiento. No verificado en un host real con systemd.
- No existen otros daemons residentes por diseño.

## 7. Pruebas ejecutadas y resultados exactos

| Prueba | Dónde | Resultado |
| --- | --- | --- |
| Tests unitarios Python 3.10 y 3.12 | GitHub Actions (workflow CI) | Pendiente de confirmar resultado real en https://github.com/octcenano/NexoraOS/actions |
| Tests locales | Este entorno | NO ejecutados: no hay intérprete Python disponible en el sandbox |
| ShellCheck / bash -n | GitHub Actions (job lint) | Pendiente de confirmar |
| Construcción de ISO | GitHub Actions (job iso-build, experimental) | Pendiente de confirmar; no ejecutable localmente (sin mkarchiso) |
| Arranque de la ISO | Ninguno | NO verificado: requiere QEMU o hardware |

## 8. Limitaciones del entorno

- Sin Python, mkarchiso, makepkg, shellcheck ni QEMU en el entorno de trabajo local.
- CI del plan gratuito puede permanecer en cola; si no llega a ejecutarse, los resultados de CI quedan sin confirmar y no se crea el tag de versión hasta tener CI verde.

## 9. Riesgos conocidos

- La ISO no se ha construido nunca de extremo a extremo: el perfil archiso es válido por estructura pero puede fallar en la primera compilación real.
- El job `iso-build` de CI es experimental y no bloquea.
- Sin pruebas contra Ollama/llama.cpp reales: la integración se ha validado con transporte falso que replica el formato de sus APIs.
