# Roadmap

Leyenda: `[x]` hecho · `[~]` parcial · `[ ]` pendiente

## Beta 0.1 — Base
- [x] Nombre e identidad inicial NEXORA OS
- [x] Arquitectura modular documentada
- [x] Modos registrados
- [x] Aislamiento de agentes definido
- [x] Perfiles híbridos prototipados
- [x] Account Hub y contratos de navegador
- [x] Pruebas unitarias base

## Beta 0.2 — Integración
- [~] Interfaz gráfica real — modelo de estado + vista de terminal; falta la ventana gráfica
- [x] Proveedor de IA local configurable — Ollama, llama.cpp, LocalAI (probado con servidor de prueba, no con modelos reales)
- [~] Almacén seguro de credenciales — RAM + `keyring` opcional (probado con doble de prueba)
- [ ] Conectores OAuth/API reales — solo ciclo de vida y permisos
- [ ] Firefox y LibreWolf probados — solo detección en PATH
- [~] Agente meteorológico conectado a fuentes verificables — Open-Meteo opt-in, no probado en vivo; AEMET pendiente

## Beta 0.3 — Sistema (esta entrega)
- [x] Watchdog del core con recuperación acotada y sin bucles infinitos
- [~] Unidades systemd — proporcionadas y endurecidas, no probadas en host real
- [x] Modo Security: auditoría defensiva de solo lectura (sin capacidades ofensivas)
- [x] Política de herramientas por modo con aprobación explícita de operaciones sensibles
- [x] Detección de GPU y almacenamiento; perfiles híbridos con prioridad manual
- [x] Configuración: claves desconocidas rechazadas, escritura segura y atómica
- [x] PKGBUILD corregido (fuente git por tag) y perfil archiso reescrito al formato actual
- [x] CI ampliada (3.10/3.12, compileall, pip check, instalación limpia, ShellCheck, bash -n, gitleaks)
- [~] Perfil archiso validado — revisado y corregido; **no compilado** (sin mkarchiso en el entorno)
- [ ] ISO generada y verificada (requiere entorno con archiso y red)
- [ ] Pruebas de instalación en VM y hardware

## Beta 0.4 — Propuesta
- [ ] Sandbox de procesos por agente (aislamiento real, no solo lógico)
- [ ] OAuth real en Account Hub
- [ ] Open-Meteo y keyring probados en vivo
- [ ] GUI: primera ventana consumiendo `render_layout()`

## Beta 1.0
- [ ] Auditoría externa
- [ ] Accesibilidad y UX/UI completas
- [ ] Actualizaciones y rollback verificados
- [ ] Documentación de instalación y recuperación
