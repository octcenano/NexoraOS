# Perfiles de escritorio y presupuesto de RAM (< 500 MB)

Objetivo: arranque en reposo por debajo de 500 MB con el stack base de NexoraOS.

| Componente | Presupuesto | Notas |
|---|---|---|
| Kernel + initramfs | 90 MB | linux-nexora con BTF, sin modulos de depuracion cargados |
| systemd + journald (volatile) | 40 MB | Storage=volatile en journald.conf |
| XFCE ligero (xfwm4 + xfce4-panel) | 150 MB | Sin compositing pesado en portatiles modestos |
| Sentinel (modo degradado /proc) | 60 MB | Con eBPF activo baja a ~45 MB al no muestrear /proc |
| Guardian + llama.cpp (modelo 1B cuantizado) | 100 MB | Solo al invocarlo; sin daemon residente |
| zram | n/a | Swap en RAM comprimido: ratio zstd ~3:1 |

Reglas:
- Lens indexa solo bajo alimentacion electrica o CPU < 20% (unidad nexora-lens.timer).
- nexora-antivirus watch limita escaneos a 5 min y usa MemoryMax=160M.
- No se permiten daemons residentes nuevos sin presupuesto de memoria documentado.
