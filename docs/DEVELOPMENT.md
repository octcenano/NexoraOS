# Guía de desarrollo — NexoraOS

## Entorno

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . && pip install build
```

Python 3.10 o superior (CI cubre 3.10 y 3.12).

## Tests

```bash
python -m unittest discover -s tests -v
```

Convenciones:

- Los tests no tocan la red: el motor IA usa un transporte inyectable (`FakeTransport` en `tests/test_ai_engine_models.py`).
- Los test del watchdog usan reloj y sleeper inyectables (sin esperas reales).
- Cada bug corregido incorpora un test de regresión.

## Estilo

- Tipado ligero con `typing`; sin dependencias externas obligatorias.
- Errores de red/IO devuelven `{"status": "error", "message": ...}` en el motor IA y estados `ok/warn/fail` en auditorías; no se lanzan excepciones al llamador de la CLI.

## Construcción

```bash
python -m build --wheel
./scripts/build-iso.sh --skip-tests   # solo si archiso está disponible
```

## CI

`.github/workflows/ci.yml`: tests en 3.10/3.12, sintaxis Python, smoke de CLI, lint (shellcheck + bash -n), gitleaks v8.21.2 fijo, build del wheel y job experimental de ISO en contenedor archlinux:base. Los resultados reales se consultan en la pestaña Actions del repositorio.

## Reglas del proyecto

- No convertir implementaciones reales en simulaciones para que pasen los tests.
- No dejar stubs ni TODOs en código crítico.
- No añadir daemons residentes sin justificación.
- Documentar en `docs/QA_REPORT.md` lo que no se puede probar.
