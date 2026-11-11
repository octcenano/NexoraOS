# Roadmap — NexoraOS

## Beta 0.4 (actual, 2026-11-11)

- Watchdog: diagnóstico sin efectos, historial de incidencias, protección anti-bucle, unidades systemd con límites. (Implementado; systemd no verificado en host real.)
- Motor IA: list_models/has_model/select_model/detect_backends, errores de conexión gestionados. (Implementado; probado con transporte falso, no contra backends reales.)
- Security: inventario de puertos, comprobación de actualizaciones, recomendaciones, informe explícito. (Implementado y probado.)
- Build ISO: artefactos antiguos eliminados, verificación del artefacto nuevo. (Implementado; ISO no construida aún.)

## Beta 0.5 (objetivo)

1. Construir y verificar la ISO en CI (job iso-build estable, sin continue-on-error) y probar arranque en QEMU.
2. Pruebas de integración contra Ollama real en CI (servicio efímero con un modelo mínimo, solo si el runner lo permite).
3. Verificar las unidades systemd en un host Arch real.
4. Primer diseño de la interfaz gráfica (maqueta + arquitectura, sin fingir implementación).
5. Instalador guiado por CLI mejorado en la ISO.

## Después

- GUI ligera (GTK/Qt según consumo) y instalador gráfico.
- Perfiles híbridos automáticos con control manual (base ya presente en profiles.py).
- Modos Creator y Office con herramientas propias.
