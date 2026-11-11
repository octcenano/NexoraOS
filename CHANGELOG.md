# Changelog

## 0.4.0-beta (2026-11-11)

### Watchdog
- Nuevo modo diagnóstico `--diagnose` (y `--json`): informe sin efectos secundarios con recomendaciones, historial de incidencias y contadores de reinicio.
- Historial de incidencias acotado (transiciones sano -> degradado por componente).
- Protección anti-bucle en modo bucle: los errores internos no derriban el proceso, pero N pasadas consecutivas con error provocan una salida controlada (código 3) para que systemd aplique su propia política de reinicio.
- Unidades systemd con límites de recursos (MemoryMax=150M, CPUQuota=5%) y endurecimiento (NoNewPrivileges, ProtectSystem=strict, ProtectKernelTunables, ProtectControlGroups).

### Motor IA local
- `list_models()`: lista modelos reales del backend (Ollama `/api/tags`, OpenAI-compatible `/v1/models`); el mock lista solo su modelo simulado.
- `has_model(model)`: comprueba disponibilidad sin descargar nada.
- `select_model(model)`: selección de modelo por usuario.
- `detect_backends()`: sondeo solo de endpoints de loopback por defecto; devuelve disponibilidad, endpoint y modelos por backend.
- Errores de conexión y respuestas inesperadas devuelven `status: error` en lugar de lanzar excepciones.

### Agente Security
- Inventario de sockets en escucha (familia y puerto, desde /proc) en lugar de un simple conteo.
- Comprobación de antigüedad de la sincronización de pacman (aviso si supera 14 días).
- Campo `recommendations` en el informe de auditoría.
- `write_report(report, path)`: única escritura del agente, explícita, atómica y con permisos 600.

### Build y packaging
- `scripts/build-iso.sh`: elimina ISOs y wheels antiguos antes de compilar, falla si `dist/` tiene más de un wheel, verifica que la ISO generada es única y válida (sha256, file, El Torito cuando isoinfo está disponible).
- Comprobaciones previas: python, python-build, archivos obligatorios del perfil archiso.
- PKGBUILD: pkgver 0.4.0. Perfil archiso: iso_version 0.4.0.

### CI
- Gitleaks fijado a la versión v8.21.2 (binario oficial) en lugar de una acción flotante.
- ShellCheck vía apt (versión gestionada por Ubuntu) con tolerancia a ausencia de scripts.
- Job experimental de construcción de ISO en contenedor archlinux:base (continue-on-error: no bloquea CI verde).

### Tests
- Tests nuevos y actualizados: watchdog (cooldown, agotamiento, incidencias, diagnóstico), motor IA (select_model, has_model, list_models, detect_backends, backend caído, respuesta inesperada), agente Security (inventario de puertos, recomendaciones, informe atómico 600).

## 0.3.0-beta

- Rama de recuperación `beta-0.3-recovery`, endurecimiento del vault, permisos por herramienta, dashboard de modos, CLI ampliada, perfil archiso y PKGBUILD iniciales, workflow CI.

## 0.2.0-beta

- Prototipo inicial: CLI, agentes base y meteorología, connectors de cuenta y navegador, core (config, permissions, profiles, registry, vault), diagnóstico de salud, dashboard de texto.
