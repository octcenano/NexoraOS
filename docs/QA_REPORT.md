# Informe QA — Beta 0.3

## 1. Bugs encontrados
1. El perfil archiso de la 0.2 no era un perfil válido: secciones `[initcpio]`/`[efi]` con claves inexistentes, sin `pacman.conf`, sin `arch`, sin `airootfs_image_type` y con `file_permissions` apuntando a ficheros de releng inexistentes.
2. `scripts/build-iso.sh` no comprobaba requisitos, no verificaba la ISO resultante y fallaba con mensajes crípticos.
3. `PKGBUILD` con tarball por tag: nombre de directorio frágil (`NexoraOS-$pkgver` no coincide con el nombre real del archivo de GitHub) y `sha256sums=('SKIP')` sin justificar.
4. Instalación limpia del wheel: la CLI no encontraba `defaults.json` sin `NEXORA_CONFIG_DIR` (corregido en 0.2.1 del repo; en 0.3 se amplía y se documenta).
5. `validate_config` aceptaba claves de primer nivel arbitrarias (fautes de frappe silenciosas, p. ej. `"tlemetry"`).
6. `nexora modes` presentaba modos stub sin distinguirlos de los funcionales.
7. `nexora profile` no informaba de GPU ni almacenamiento.

## 2. Bugs corregidos en esta versión
- 1: perfil archiso reescrito al formato actual (con `pacman.conf`, `arch`, `airootfs_image_type`, `file_permissions` coherentes y `airootfs/` completo).
- 2: script reescrito con comprobaciones previas, mensajes comprensibles y verificación posterior (sha256, `file`, isoinfo).
- 3: fuente git fijada por tag (`#tag=v$pkgver`); SKIP documentado como aceptable para fuente git.
- 5: claves desconocidas rechazadas; contenedores validados por tipo.
- 6: `modes` muestra el estado real por modo; `dashboard` también (`mode_status`).
- 7: detección de GPU y almacenamiento añadida y mostrada.

## 3. Bugs pendientes
- Ninguno conocido abierto de los detectados; los riesgos activos están en la sección 10.

## 4. Problemas de UX/UI
- La GUI sigue sin existir: la vista de terminal es funcional pero no es la experiencia final. Se renovó el estilo (marco fino, estados declarados, sin estética de terminal verde clásica).
- Sin estados de carga ni vacíos más allá de los mensajes de error de la CLI.
- Accesibilidad: salida de texto plano (compatible con lectores de pantalla básicos), sin dependencia de color; pendiente i18n y tamaños de pantalla pequeños (GUI futura).
- `nexora --help` ahora incluye ejemplos.

## 5. Problemas de seguridad
- Sin secretos en texto plano: la configuración los rechaza y el vault es la única vía (RAM o keyring del SO).
- La auditoría del modo Security es de solo lectura y sin capacidades ofensivas (verificado por test que compara el árbol de archivos antes/después).
- `ToolPolicy` bloquea herramientas no declaradas y exige aprobación explícita para operaciones sensibles.
- Endpoints IA remotos siguen rechazados salvo `allow_remote=True`.
- Pendiente: sandbox de procesos por agente (el aislamiento sigue siendo lógico) y OAuth real.

## 6. Estado de watchdogs y daemons
- `nexora.watchdog`: implementado y probado (recuperación acotada, cooldown, log acotado, excepciones de check contenidas).
- Unidades systemd (sistema y usuario): proporcionadas y endurecidas (NoNewPrivileges, ProtectSystem=strict, Restart acotado), **no probadas en un host real**.
- No hay servicios residentes por defecto.

## 7. Pruebas ejecutadas
En este entorno de trabajo NO hay intérprete de Python, por lo que la suite no se ha ejecutado localmente. Lo que sí se ha hecho:
- Revisión estática completa de todos los módulos modificados.
- Los tests nuevos y modificados están escritos para `python -m unittest discover -s tests`.
- CI (GitHub Actions) ejecuta en cada push: Python 3.10 y 3.12, `compileall`, `pip check`, unittest, smoke tests de CLI, instalación limpia del wheel, ShellCheck, `bash -n` y gitleaks.

## 8. Resultados exactos
- Local: no aplicable (sin Python en el entorno; documentado, no inventado).
- CI: pendiente de la primera ejecución en GitHub tras este push; el resultado real quedará registrado en la pestaña Actions.

## 9. Limitaciones del entorno
- Sin intérprete de Python, sin `makepkg`, sin `mkarchiso`, sin ShellCheck, sin red para descargar paquetes y sin utilidades zip/tar: no se pudo ejecutar la suite, compilar el paquete pacman ni generar/verificar la ISO.
- No se puede crear el ZIP de la entrega en este entorno; la entrega es el commit en GitHub (clonable y verificable por SHA).

## 10. Riesgos conocidos
- La ISO no se ha generado nunca: la primera compilación real puede revelar ajustes (mirrors, tamaño, arranque seguro).
- Open-Meteo y `keyring` sin pruebas en vivo.
- Aislamiento de agentes lógico, no de procesos.
- Los límites de los perfiles siguen siendo orientativos, no medidos.
- Las unidades systemd no probadas en host real.
