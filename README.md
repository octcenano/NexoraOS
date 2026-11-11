# NEXORA OS â Beta 0.2

NEXORA es una plataforma modular de sistema operativo y entorno de agentes. Esta entrega es una **base de desarrollo ejecutable en Python**, no una ISO instalable ni un sistema operativo completo.

## QuÃ© es real y quÃ© no (Beta 0.2)

| Componente | Estado |
|---|---|
| Registro de modos y agentes con memoria privada por modo | Real (aislamiento **lÃ³gico**, sin sandbox de procesos) |
| Mensajes entre agentes con aprobaciÃ³n explÃ­cita del usuario | Real |
| Perfiles hÃ­bridos con detecciÃ³n de hardware y prioridad manual | Real |
| ConfiguraciÃ³n validada (rechaza secretos, fija polÃ­ticas) | Real |
| Account Hub: ciclo de vida y permisos de conexiones | Real. **Sin OAuth real** todavÃ­a |
| Motor IA local: Ollama, llama.cpp, LocalAI | Real, probado contra un servidor HTTP de prueba. Por defecto usa `local_mock` (simulado) |
| Vault de secretos | Real: RAM por defecto; almacÃ©n del SO con `keyring` opcional |
| Agente meteorolÃ³gico | Simulado por defecto. Open-Meteo real y opt-in (`--live`), **no probado en vivo** |
| Dashboard | Modelo de estado + vista de terminal. **No hay ventana grÃ¡fica** |
| DiagnÃ³stico | Comprobaciones reales; watchdogs/systemd/ISO: pendientes |

## Ejecutar (desde la raÃ­z del proyecto, Python 3.10+)

```bash
python -m nexora modes
python -m nexora profile                 # detecta tu hardware
python -m nexora profile --profile expanded --cpu-cores 2 --ram-gb 4   # avisa de que supera lo recomendado
python -m nexora dashboard [--mode meteorology] [--json]
python -m nexora health
python -m nexora weather Madrid          # simulado
python -m nexora weather Madrid --live   # Open-Meteo (envÃ­a la ubicaciÃ³n a un servicio externo)
python -m nexora ask "hola" --mode forge
python -m unittest discover -s tests -v
```

## ConfiguraciÃ³n

- `config/defaults.json`: valores por defecto. Es la Ãºnica fuente de la versiÃ³n junto a `nexora/__version__`.
- ConfiguraciÃ³n de usuario opcional: `~/.config/nexora/user.json` (o `NEXORA_USER_CONFIG`). Ver `config/user.example.json`.
- La configuraciÃ³n **rechaza** claves que parezcan secretos (`password`, `token`, `api_key`â¦) y URLs con credenciales. Los secretos van en el vault.
- Si instalas el paquete con `pip install .`, define `NEXORA_CONFIG_DIR` apuntando a una carpeta con `defaults.json` (el empaquetado de datos queda para Beta 0.3).

### Usar un modelo local real

```json
{ "ai_engine": { "backend": "ollama", "model": "llama3.2" } }
```

Backends: `ollama`, `llamacpp`, `localai`. Solo se aceptan endpoints locales (loopback) salvo `"allow_remote": true`.

### Guardar secretos fuera de la RAM

```bash
pip install keyring        # y un almacÃ©n de secretos del sistema (p. ej. gnome-keyring o KWallet)
```
```json
{ "vault": { "backend": "keyring" } }
```

## Importante

Esta beta no instala Arch, no genera una ISO, no conecta cuentas automÃ¡ticamente y no contiene credenciales. Los conectores reales requieren implementar OAuth/API oficial y probarlos en cada navegador. Ver `docs/QA_REPORT.md` para lo verificado y lo no verificado.
