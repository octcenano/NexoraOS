# Changelog

## 0.2.0-beta (revisado)

Corrige el paquete anterior, cuyo cÃ³digo no coincidÃ­a con el documento de traspaso y cuya suite de tests no arrancaba.

### Corregido
- Los tests importaban `ModeRegistry`, `calculate_hybrid_profile` y `BaseAgent`, que no existÃ­an; `AccountHub` y `BrowserConnector` tenÃ­an otra API distinta a la usada por los tests. Ahora existen y los 9 tests originales pasan sin modificarse.
- `MeteorologyAgent` importaba una clase inexistente y devolvÃ­a datos fijos presentados como "observaciÃ³n verificada". Ahora los datos simulados se etiquetan `simulated: True` y existe un proveedor real (Open-Meteo, opt-in).
- `LocalAIEngine` afirmaba soportar Ollama/llama.cpp/LocalAI pero solo devolvÃ­a texto simulado, y `is_connected` era siempre `True`. Ahora implementa los tres backends.
- `SecureVault` era un diccionario sin polÃ­tica ni validaciÃ³n; ahora tiene backends explÃ­citos y no filtra valores en `repr`.
- La CLI usaba funciones que no existÃ­an y valores fijos (4 nÃºcleos, 8 GB); ahora detecta el hardware.
- `defaults.json` y `pyproject.toml` seguÃ­an en 0.1; ahora la versiÃ³n sale de `nexora.__version__`.
- Faltaban `__init__.py` en 4 subpaquetes; el zip tenÃ­a una carpeta duplicada anidada.
- `diagnostics.health` devolvÃ­a estados fijos; ahora hace comprobaciones reales (aislamiento, config, vault, motor IA, navegadores).

### AÃ±adido
- `core.config` (carga y validaciÃ³n; rechaza secretos), `AgentMessage` y `share_with` con aprobaciÃ³n explÃ­cita, estados y permisos reales en el Account Hub, comandos CLI `health`, `weather`, `ask`, opciones `dashboard --mode/--json`, 66 tests nuevos.
- `IsolatedAgent` se sustituye por `BaseAgent` (con memoria `remember/recall`).
