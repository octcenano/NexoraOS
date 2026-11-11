"""Vista GTK3 de Nexora Desktop (importación diferida).

Requisitos reales: PyGObject (python-gobject) y GTK3. Si faltan, la
importación falla con un mensaje claro y los modelos siguen usables por CLI.

Diseño: tema oscuro por defecto, acento configurable, sin decoración
excesiva. Los estados de cada sección (ok, no_data, unavailable, error) se
muestran textualmente: nunca se presentan datos inexistentes como reales.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

STATE_LABELS = {
    "ok": "OK",
    "no_data": "Sin datos",
    "unavailable": "No disponible",
    "error": "Error",
    "not_implemented": "Pendiente",
    "declared": "Declarado",
    "empty": "Vacío",
    "no_results": "Sin resultados",
}

ACCENT_DEFAULT = "#3a7bd5"

GTK_CSS = """
:root {{ --accent: {accent}; }}
window {{ background: #1e2229; color: #e6e6e6; }}
headerbar {{ background: #262b33; }}
.accent {{ color: {accent}; }}
.dimmed {{ color: #9aa0a8; }}
button {{ border-radius: 6px; }}
"""


def _format_section(section: Dict[str, Any]) -> str:
    state = section.get("state", "error")
    label = STATE_LABELS.get(state, state)
    data = section.get("data")
    if state != "ok" or data is None:
        return f"[{label}] {section.get('message', '')}".strip()
    return f"[{label}] {data}"


def run(app) -> int:
    """Ejecuta la ventana principal. Requiere gi (PyGObject) y sesión gráfica."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    win = Gtk.Window(title="Nexora Desktop")
    win.set_default_size(960, 640)
    win.set_position(Gtk.WindowPosition.CENTER)

    header = Gtk.HeaderBar(title="Nexora Desktop", subtitle="XFCE + Nexora")
    header.set_show_close_button(True)
    win.set_titlebar(header)

    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
    stack_switcher = Gtk.StackSwitcher(stack=stack)

    # --- Dashboard ---
    dash_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    for name, section in app.dashboard.snapshot().items():
        row = Gtk.Label(label=name, xalign=0)
        row.get_style_context().add_class("accent")
        value = Gtk.Label(label=_format_section(section), xalign=0)
        dash_box.pack_start(row, False, False, 0)
        dash_box.pack_start(value, False, False, 0)
    scroll = Gtk.ScrolledWindow()
    scroll.add(dash_box)
    stack.add_titled(scroll, "dashboard", "Dashboard")

    # --- Mode Center ---
    mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    ov = app.mode_center.overview()
    mode_box.pack_start(Gtk.Label(label="Modos activos: " + ", ".join(ov["active_modes"]), xalign=0),
                        False, False, 0)
    grid = Gtk.Grid(column_spacing=6, row_spacing=6, border_width=12)
    col = 0
    for mode in app.registry.names():
        btn = Gtk.Button(label=mode)
        btn.connect("clicked", lambda _b, m=mode: (app.mode_center.activate(m),
                                                   stack.queue_draw()))
        grid.attach(btn, col, 0, 1, 1)
        col += 1
    mode_box.pack_start(grid, False, False, 0)
    stack.add_titled(mode_box, "mode_center", "Modos")

    # --- NKE Control ---
    nke_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    nke_ov = app.nke_control.overview()
    nke_box.pack_start(Gtk.Label(label="Kernel: " + str(nke_ov.get("kernel_release")), xalign=0),
                       False, False, 0)
    nke_box.pack_start(Gtk.Label(label="Ciclos: " + str(nke_ov.get("cycles")), xalign=0), False, False, 0)
    for p in nke_ov.get("pending_supervised", []):
        nke_box.pack_start(Gtk.Label(label=f"Pendiente: {p['kind']} en {p['target']}", xalign=0),
                           False, False, 0)
    approve_btn = Gtk.Button(label="Ejecutar ciclo de diagnóstico")
    approve_btn.connect("clicked", lambda _b: (app.nke_control.refresh(), stack.queue_draw()))
    nke_box.pack_start(approve_btn, False, False, 0)
    stack.add_titled(nke_box, "nke_control", "Kernel Engine")

    # --- Hub ---
    hub_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    agents = app.hub.agents(app.registry)["agents"]
    for a in agents:
        hub_box.pack_start(Gtk.Label(label=f"{a['name']} ({a['kind']}): {a['status']}", xalign=0),
                           False, False, 0)
    stack.add_titled(hub_box, "hub", "Hub")

    # --- System Center ---
    sys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    for name, section in app.system_center.sections().items():
        sys_box.pack_start(Gtk.Label(label=section["label"], xalign=0), False, False, 0)
        for entry in section["entries"]:
            label = f"  {entry['label']} [{STATE_LABELS.get(entry['state'], entry['state'])}]"
            sys_box.pack_start(Gtk.Label(label=label, xalign=0), False, False, 0)
    stack.add_titled(sys_box, "system_center", "Sistema")

    header.set_custom_title(stack_switcher)
    win.add(stack)

    # Tema oscuro y acento (CSS del tema Nexora si existe; CSS integrado si no).
    settings = Gtk.Settings.get_default()
    if settings is not None:
        settings.set_property("gtk-application-prefer-dark-theme", True)
    provider = Gtk.CssProvider()
    theme_css = GTK_CSS.format(accent=ACCENT_DEFAULT)
    theme_path = Path("/usr/share/themes/Nexora-Dark/gtk-3.0/gtk.css")
    if theme_path.exists():
        try:
            theme_css = theme_path.read_text(encoding="utf-8")
        except OSError:
            pass
    try:
        provider.load_from_data(theme_css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            win.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    except GLib.Error:
        pass  # CSS inválido no debe impedir el arranque; se usa el tema base

    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0
