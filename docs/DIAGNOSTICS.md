# Guía de diagnóstico — NexoraOS

## Diagnóstico del core

```bash
nexora health
```

Comprueba configuración, bóveda, aislamiento de memoria entre agentes y disponibilidad del motor IA.

## Watchdog

```bash
nexora-watchdog                 # una pasada, estado general
nexora-watchdog --diagnose      # informe sin efectos: incidencias, reinicios, recomendaciones
nexora-watchdog --diagnose --json
```

Interpretación:

- `overall: ok`: todos los componentes sanos.
- `overall: degraded`: algún componente falla pero puede recuperarse.
- `overall: failed`: componente con reinicios agotados; el informe indica cuál y recomienda revisión manual.

El watchdog nunca modifica configuración ni políticas: solo ejecuta la recuperación registrada por el propio componente y, en caso de agotamiento, recomienda intervención manual.

## Modo bucle (systemd)

```bash
nexora-watchdog --loop 300 --max-loop-errors 3
journalctl --user -u nexora-watchdog -f
```

Si el propio watchdog falla internamente 3 pasadas seguidas, sale con código 3 y systemd aplica su política de reinicio (RestartSec=30, máximo 5 arranques en 10 minutos). Así se evita un bucle de reinicios infinito.

## Motor IA

```bash
python - <<'EOF'
from nexora.core.ai_engine import detect_backends
print(detect_backends())
EOF
```

Devuelve, por backend (ollama, llamacpp, localai), si está disponible en su endpoint de loopback por defecto y qué modelos expone. Si un backend está caído, `nexora` responde con `status: error` y mensaje accionable en lugar de bloquearse.

## Seguridad

```bash
nexora security audit
nexora security report informe.json   # escritura explícita, permisos 600
```

La auditoría es de solo lectura: configuración y secretos, permisos de `user.json`, sockets en escucha, antigüedad de la sincronización de pacman y ficheros escribibles por otros en `~/.config/nexora`.
