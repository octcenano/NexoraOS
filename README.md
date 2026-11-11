# NEXORA OS — Beta 0.3

NEXORA es una plataforma modular de sistema operativo y entorno de agentes. Esta entrega sigue siendo una **base de desarrollo ejecutable en Python** (base Arch para el empaquetado), no una ISO instalable ni un sistema operativo completo.

## Qué es real, qué está probado y qué no (Beta 0.3)

| Componente | Estado | Probado |
|---|---|---|
| Registro de modos y agentes con memoria privada por modo | Implementado (aislamiento **lógico**, sin sandbox de procesos) | Sí (tests) |
| Mensajes entre agentes con aprobación explícita | Implementado | Sí (tests) |
| Política de herramientas por modo (`ToolPolicy`) con operaciones sensibles sujetas a aprobación | Implementado | Sí (tests) |
| Perfiles híbridos: detección de CPU, RAM, GPU y almacenamiento | Implementado (GPU/almacenamiento solo verificado en CI Linux) | Parcial |
| Configuración validada (rechaza secretos y claves desconocidas; escritura segura atómica) | Implementado | Sí (tests) |
| Account Hub: ciclo de vida y permisos | Implementado. **Sin OAuth real** todavía | Sí (tests) |
| Motor IA local: Ollama, llama.cpp, LocalAI + `list_models()` | Implementado, probado contra servidores HTTP de prueba. Por defecto `local_mock` (simulado) | Sí (tests, sin modelos reales) |
| Vault de secretos | Implementado: RAM por defecto; almacén del SO con `keyring` (probado con doble de prueba) | Parcial |
| Agente meteorológico | Simulado por defecto. Open-Meteo real y opt-in (`--live`), **no probado en vivo** | Parcial |
| Modo Security: auditoría defensiva de solo lectura (`nexora audit`) | Implementado | Sí (tests) |
| Watchdog del core (`nexora.status` / `nexora-watchdog`): comprobaciones reales, recuperación acotada, sin bucles infinitos | Implementado como módulo y comando; **no residente por defecto** | Sí (tests) |
| Unidades systemd (sistema y usuario) para el watchdog | Proporcionadas, **no probadas en un host real** | No |
| Dashboard | Modelo de estado + vista de terminal renovada. **No hay ventana gráfica** | Parcial |
| PKGBUILD (fuente git fijada por tag) y perfil archiso | Revisados y corregidos; **no compilados en este entorno** (sin makepkg ni mkarchiso) | No |
| ISO | **No generada ni verificada** en este entorno. `scripts/build-iso.sh` incluye comprobaciones previas y verificación posterior (sha256, `file`, isoinfo) | No |

## Ejecutar (desde la raíz del proyecto, Python 3.10+)

```bash
python -m nexora modes
python -m nexora profile                 # detecta CPU, RAM, GPU y almacenamiento
python -m nexora dashboard [--mode meteorology] [--json]
python -m nexora health
python -m nexora status                  # watchdog: una pasada de supervisión
python -m nexora audit                   # auditoría defensiva (solo lectura)
python -m nexora weather Madrid          # simulado
python -m nexora weather Madrid --live   # Open-Meteo (envía la ubicación a un servicio externo)
python -m nexora ask "hola" --mode forge
python -m unittest discover -s tests -v
```

## Configuración

- `config/defaults.json`: valores por defecto. La versión debe coincidir con `nexora.__version__`.
- Configuración de usuario opcional: `~/.config/nexora/user.json` (o `NEXORA_USER_CONFIG`). Ver `config/user.example.json`.
- Búsqueda de `defaults.json` en orden: `NEXORA_CONFIG_DIR`, `config/` del proyecto, copia incluida en el paquete Python, `/usr/share/nexora/config`. Una instalación limpia funciona sin variables de entorno.
- La configuración **rechaza** secretos (`password`, `token`, `api_key`…), URLs con credenciales y **claves de primer nivel desconocidas**.
- `python -c "from nexora.core.config import write_user_config, load_config; write_user_config(load_config())"` escribe la config de usuario de forma atómica con permisos 600/700.

### Usar un modelo local real

```json
{ "ai_engine": { "backend": "ollama", "model": "llama3.2" } }
```

Backends: `ollama`, `llamacpp`, `localai`. Solo se aceptan endpoints locales (loopback) salvo `"allow_remote": true`. `nexora health` comprueba la conectividad; `LocalAIEngine.list_models()` lista los modelos disponibles.

### Watchdog como servicio (opcional)

```bash
sudo pacman -S nexora-os            # instala la unidad en /usr/lib/systemd
sudo useradd -r -s /usr/bin/nologin nexora
sudo systemctl enable --now nexora-watchdog
```

El watchdog no es residente por defecto: `nexora status` hace una pasada. El servicio opcional usa `Restart=on-failure` con límites (`StartLimitBurst=5`) y el propio watchdog acota los reinicios por componente (`max_restarts=3`); nunca modifica configuración.

### Empaquetado e ISO (base Arch)

```bash
cd packaging/arch && makepkg -si    # paquete pacman
./scripts/build-iso.sh              # wheel + tests + ISO (requiere archiso y root)
```

Ver `packaging/README.md` y `docs/QA_REPORT.md` para lo verificado y lo pendiente.

## Importante

Esta beta no instala Arch, no genera una ISO verificada, no conecta cuentas automáticamente y no contiene credenciales. Los conectores reales requieren implementar OAuth/API oficial y probarlos en cada navegador. El modo Security es exclusivamente defensivo y de solo lectura.
