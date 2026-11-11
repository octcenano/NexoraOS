# Informe QA â Beta 0.2

## Verificado en esta revisiÃ³n
- `python -m unittest discover -s tests -v` â **75 tests, OK** (Python 3.12.3, Linux). Incluye los 9 tests originales sin modificar y 66 nuevos.
- Los tests detectan roturas reales: se rompieron a propÃ³sito el aislamiento de memoria, la comprobaciÃ³n de endpoints locales y la regla de autorizaciÃ³n del Account Hub, y cada rotura hizo fallar la suite.
- El motor IA (Ollama y API compatible con OpenAI) se probÃ³ contra un servidor HTTP local que imita el formato de esas APIs.
- Open-Meteo se probÃ³ con respuestas simuladas inyectadas.
- `keyring` se probÃ³ con un doble de prueba.
- El paquete se construye (`pip wheel`, versiÃ³n `0.2.0b0`) y se instala; fuera del repo necesita `NEXORA_CONFIG_DIR`.
- Sin credenciales reales ni tokens en el paquete; el validador de configuraciÃ³n rechaza secretos.

## NO verificado
- Open-Meteo real (el entorno de pruebas no tenÃ­a red).
- Ollama, llama.cpp o LocalAI reales con un modelo cargado.
- `keyring` real con un almacÃ©n de secretos del sistema.
- Python 3.10 y 3.11 (solo se probÃ³ 3.12).
- Firefox/LibreWolf (solo se detecta si hay un ejecutable en el PATH).
- Arch Linux ni hardware fÃ­sico.

## Limitaciones conocidas
- No es una ISO ni instala un sistema operativo; no hay instalador.
- No hay ventana grÃ¡fica: el dashboard es un modelo de estado y una vista de terminal.
- No hay OAuth ni integraciÃ³n real con navegadores.
- AEMET OpenData no estÃ¡ implementado.
- El aislamiento de agentes es lÃ³gico, no de procesos.
- Forge, Security, Creator y Office son agentes stub.
- Watchdogs y demonios systemd siguen pendientes.
- Los lÃ­mites por perfil son orientativos, no medidos.

## RevisiÃ³n UX/UI
La interfaz grÃ¡fica aÃºn no estÃ¡ implementada. La CLI y la vista de terminal sirven para validar modos, perfiles y estado; no representan la experiencia final.
