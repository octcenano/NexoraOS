# Roadmap

Leyenda: `[x]` hecho Â· `[~]` parcial Â· `[ ]` pendiente

## Beta 0.1 â Base
- [x] Nombre e identidad inicial NEXORA OS
- [x] Arquitectura modular documentada
- [x] Modos registrados
- [x] Aislamiento de agentes definido
- [x] Perfiles hÃ­bridos prototipados
- [x] Account Hub y contratos de navegador
- [x] Pruebas unitarias base

## Beta 0.2 â IntegraciÃ³n
- [~] Interfaz grÃ¡fica real â modelo de estado + vista de terminal; falta la ventana grÃ¡fica
- [x] Proveedor de IA local configurable â Ollama, llama.cpp, LocalAI (probado con servidor de prueba, no con modelos reales)
- [~] AlmacÃ©n seguro de credenciales â RAM + `keyring` opcional (probado con doble de prueba)
- [ ] Conectores OAuth/API reales â solo ciclo de vida y permisos
- [ ] Firefox y LibreWolf probados â solo detecciÃ³n en PATH
- [~] Agente meteorolÃ³gico conectado a fuentes verificables â Open-Meteo opt-in, no probado en vivo; AEMET pendiente

## Beta 0.3 â Sistema
- [ ] Cerrar los pendientes de Beta 0.2 (arriba)
- [ ] Base Arch/ISO reproducible
- [ ] Instalador grÃ¡fico
- [ ] Servicios systemd mÃ­nimos y medidos
- [ ] Watchdogs con lÃ­mites y recuperaciÃ³n segura
- [ ] Pruebas de instalaciÃ³n en VM y hardware

## Beta 1.0
- [ ] AuditorÃ­a externa
- [ ] Accesibilidad y UX/UI completas
- [ ] Actualizaciones y rollback verificados
- [ ] DocumentaciÃ³n de instalaciÃ³n y recuperaciÃ³n
