# Nexora Desktop

Entorno gráfico propio de NEXORA OS. Decisión arquitectónica definitiva: **XFCE + Nexora Desktop**. XFCE es la base (panel, gestor de ventanas, ajustes, notificaciones, sesión); Nexora Desktop añade una capa propia integrada, no un escritorio nuevo ni un tema suelto.

## Arquitectura

| Módulo | Archivo | Función |
|---|---|---|
| Nexora Shell | `nexora/desktop/shell.py` | Índice de aplicaciones real (.desktop), búsqueda global, diseño del panel, notificaciones (notify-send), escritorios virtuales declarativos |
| Nexora Dashboard | `nexora/desktop/dashboard.py` | CPU, RAM/swap, GPU, temperatura, almacenamiento, red, batería, procesos, servicios y actividad de Core/NKE. Datos reales de /proc y /sys con estados explícitos |
| Nexora Mode Center | `nexora/desktop/mode_center.py` | Activar, combinar y desactivar los cinco modos oficiales, intensidad 1/2/3/full, cambios previstos (plan real de build_allocation), conflictos y recuperación de la configuración anterior |
| Nexora NKE Control | `nexora/desktop/nke_control.py` | Estado del motor, capacidades del kernel, eBPF (con degradación declarada), políticas, acciones pendientes, aprobación/rechazo, deshacer, historial y huella del propio NKE |
| Nexora Hub | `nexora/desktop/hub.py` | Agentes (modos y especialistas), modelos IA por proveedor (sondeo loopback real) y herramientas instaladas por categoría |
| Nexora System Center | `nexora/desktop/system_center.py` | Secciones del sistema que reutilizan herramientas de XFCE y Linux con lista blanca de comandos |
| Orquestador | `nexora/desktop/app.py` | Ciclo de vida, eventos, modelo completo para la vista, arranque GTK diferido. Nunca como root |
| Vista GTK3 | `nexora/desktop/gtkui.py` | Ventana con pestañas por módulo, tema oscuro y acento; importación diferida de PyGObject |

Separación modelo/vista: los modelos no dependen de GTK y se prueban en CI; la vista (`gtkui`) requiere `python-gobject`, `gtk3` y una sesión gráfica. Si falta algo, el error es explícito (`nexora desktop --gtk` devuelve código 4 con el motivo) y el modelo sigue disponible con `nexora desktop --json`.

## Estados de interfaz

Cada sección declara su estado: `ok`, `no_data` (sin datos, p. ej. sin batería), `unavailable` (herramienta no instalada), `error`, `not_implemented` (sección pendiente, sin botón falso), `declared` (configuración que se aplica dentro de una sesión XFCE). No hay porcentajes inventados ni datos simulados presentados como reales.

## Seguridad

- La interfaz nunca se ejecuta como root (`NexoraDesktopApp` lo rechaza).
- Ningún comando arbitrario: System Center y las notificaciones usan listas fijas y ejecución sin shell.
- Las acciones sensibles del NKE (categoría B) solo se aplican con aprobación explícita mediante `NKEngine.approve_proposal()`, que valida categoría, objetivo y reversibilidad, y registra la decisión. La categoría C nunca se ejecuta.
- Los proveedores de IA se sondean solo en loopback; un endpoint remoto exige configuración explícita.

## Integración con XFCE

- `packaging/xfce/nexora-session.sh`: sesión con recuperación. Tres fallos en 60 segundos devuelven el escritorio XFCE estándar y limpian procesos de la capa Nexora.
- `packaging/xfce/autostart/nexora-desktop.desktop`: arranque automático de la ventana principal.
- `packaging/xfce/panel-layout.sh` y `apply-appearance.sh`: aplican panel y apariencia con xfconf-query (requieren sesión activa; fallan con mensaje claro si no).
- `packaging/xfce/themes/Nexora-Dark/`: tema GTK3 oscuro con acento.

## Instalación

El PKGBUILD instala la sesión (`/usr/bin/nexora-session`), el autostart, los scripts xfconf y el tema. Dependencias opcionales: `xfce4`, `python-gobject`, `gtk3`, `libnotify`. La ISO incluye la pila XFCE (`packaging/archiso/packages.x86_64`).

## Rendimiento

Objetivos (a verificar con mediciones reales en hardware de destino, no declarados todavía): la ventana principal es un único proceso de usuario, sin daemons adicionales por panel, y el panel de XFCE gestiona el resto. El consumo en reposo se medirá cuando exista un entorno XFCE real disponible; hasta entonces no se publican cifras.

## Limitaciones honestas

- La vista GTK3 no se ha ejecutado en este entorno (sin PyGObject ni sesión gráfica): está probada su ausencia controlada, no su comportamiento visual.
- El diseño fino del panel de XFCE (plugin-ids) se edita con xfce4-panel en modo de edición; los scripts xfconf aplican lo básico.
- Las secciones "Usuarios", "Actualizaciones" y "Servicios" del System Center están declaradas como pendientes: requieren integración con polkit y no muestran botones falsos.
- El arranque de la sesión en la ISO no está verificado: hace falta una máquina virtual con la ISO construida.
