"""Vista GTK3 de Nexora Desktop (importación diferida).

Requisitos reales: PyGObject (python-gobject) y GTK3. Si faltan, la
importación de este módulo sigue siendo segura (gi se importa dentro de
run()) y los modelos siguen usables por CLI.

Actualización dinámica real: un temporizador de GLib (timeout_add) agenda
instantáneas periódicas; las operaciones lentas (ciclo del NKE, aprobaciones,
deshacer, activación de modos) se ejecutan en un hilo de trabajo
(AsyncRunner) y su resultado se aplica en el hilo gráfico mediante
GLib.idle_add. Las etiquetas se refrescan desde los modelos en cada
instantánea: nunca quedan fijas a una captura inicial.

Los controles del NKE son reales (aprobar, rechazar, deshacer, historial,
estado de cada ajuste e impacto previsto) y exigen confirmación explícita
del usuario antes de cambiar el estado del sistema. Las acciones sin
implementación segura se muestran como "No disponible" y no ofrecen botones
de ejecución.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from nexora.desktop.nke_panel import AsyncRunner, NkePanelModel, Poller

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
REFRESH_INTERVAL_MS = 2000

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

    panel = NkePanelModel(app.nke_control)

    def once(cb):
        """Envuelve una devolución para que GLib.idle_add la ejecute una vez."""
        def inner():
            cb()
            return False
        return inner

    runner = AsyncRunner(deliver=lambda cb: GLib.idle_add(once(cb)))

    win = Gtk.Window(title="Nexora Desktop")
    win.set_default_size(960, 640)
    win.set_position(Gtk.WindowPosition.CENTER)

    header = Gtk.HeaderBar(title="Nexora Desktop", subtitle="XFCE + Nexora")
    header.set_show_close_button(True)
    win.set_titlebar(header)

    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
    stack_switcher = Gtk.StackSwitcher(stack=stack)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    status = Gtk.Label(label="Cargando...", xalign=0)
    status.get_style_context().add_class("dimmed")

    def set_status(text: str) -> None:
        status.set_text(text)

    def run_slow(fn, on_done, doing: str) -> None:
        """Ejecuta fn en un hilo de trabajo; la interfaz nunca se bloquea."""
        set_status(doing + "...")
        runner.submit(fn, on_done=on_done,
                      on_error=lambda exc: set_status(doing + ": Error: " + str(exc)))

    # --- Dashboard ---------------------------------------------------------
    dash_rows: Dict[str, Any] = {}
    dash_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    for name, section in app.dashboard.snapshot().items():
        title_lbl = Gtk.Label(label=name, xalign=0)
        title_lbl.get_style_context().add_class("accent")
        value_lbl = Gtk.Label(label=_format_section(section), xalign=0)
        dash_box.pack_start(title_lbl, False, False, 0)
        dash_box.pack_start(value_lbl, False, False, 0)
        dash_rows[name] = value_lbl
    dash_scroll = Gtk.ScrolledWindow()
    dash_scroll.add(dash_box)
    stack.add_titled(dash_scroll, "dashboard", "Dashboard")

    def update_dashboard(snapshot: Dict[str, Any]) -> None:
        for name, section in snapshot.items():
            text = _format_section(section)
            lbl = dash_rows.get(name)
            if lbl is None:
                title_lbl = Gtk.Label(label=name, xalign=0)
                title_lbl.get_style_context().add_class("accent")
                lbl = Gtk.Label(label=text, xalign=0)
                dash_box.pack_start(title_lbl, False, False, 0)
                dash_box.pack_start(lbl, False, False, 0)
                dash_rows[name] = lbl
                dash_box.show_all()
            else:
                lbl.set_text(text)

    # --- Modos -------------------------------------------------------------
    mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    modes_label = Gtk.Label(label="Modos activos: cargando...", xalign=0)
    mode_box.pack_start(modes_label, False, False, 0)
    grid = Gtk.Grid(column_spacing=6, row_spacing=6, border_width=12)

    def activate_mode(_btn, mode: str) -> None:
        def done(res):
            set_status("Modo " + mode + ": " + str(res.get("state", res)))
        run_slow(lambda: app.mode_center.activate(mode), done, "Activando modo " + mode)

    col = 0
    for mode in app.registry.names():
        btn = Gtk.Button(label=mode)
        btn.connect("clicked", activate_mode, mode)
        grid.attach(btn, col, 0, 1, 1)
        col += 1
    mode_box.pack_start(grid, False, False, 0)
    stack.add_titled(mode_box, "mode_center", "Modos")

    def update_modes(ov: Dict[str, Any]) -> None:
        activos = ", ".join(ov.get("active_modes", [])) or "ninguno"
        modes_label.set_text("Modos activos: " + activos)

    # --- NKE Control ---------------------------------------------------------
    nke_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, border_width=12)
    nke_header = Gtk.Label(label="Kernel Engine: cargando...", xalign=0)
    nke_pol_label = Gtk.Label(label="", xalign=0)
    nke_pol_label.get_style_context().add_class("dimmed")
    nke_pending_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    nke_mods_label = Gtk.Label(label="", xalign=0)
    nke_mods_label.get_style_context().add_class("dimmed")
    nke_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    cycle_btn = Gtk.Button(label="Ejecutar ciclo de diagnóstico")
    undo_btn = Gtk.Button(label="Deshacer último ajuste")
    history_btn = Gtk.Button(label="Historial")
    for b in (cycle_btn, undo_btn, history_btn):
        nke_buttons.pack_start(b, False, False, 0)
    for w in (nke_header, nke_pol_label, nke_pending_box, nke_mods_label, nke_buttons):
        nke_box.pack_start(w, False, False, 0)
    stack.add_titled(nke_box, "nke_control", "Kernel Engine")

    def confirm(title: str, text: str) -> bool:
        dlg = Gtk.MessageDialog(transient_for=win, flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.OK_CANCEL, text=title)
        dlg.format_secondary_text(text)
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.OK

    def approve_flow(_btn, p: Dict[str, Any]) -> None:
        kind, target = p["kind"], p["target"]
        texto = ("Se aplicará: " + (p.get("impact") or p.get("description") or kind)
                 + ". Objetivo: " + str(target)
                 + ". Reversible: " + ("sí" if p.get("reversible") else "no") + ".")
        if not confirm("¿Aprobar " + kind + "?", texto):
            set_status("Aprobación cancelada por el usuario")
            return

        def done(res):
            set_status("Aprobar " + kind + ": " + str(res.get("state", res)))
        run_slow(lambda: panel.approve(kind, target, confirmed=True), done,
                 "Aprobando " + kind)

    def reject_flow(_btn, p: Dict[str, Any]) -> None:
        kind, target = p["kind"], p["target"]
        if not confirm("¿Rechazar " + kind + "?",
                       "La propuesta se descarta y la decisión queda registrada. "
                       "Objetivo: " + str(target) + "."):
            set_status("Rechazo cancelado por el usuario")
            return

        def done(res):
            set_status("Rechazar " + kind + ": " + str(res.get("state", res)))
        run_slow(lambda: panel.reject(kind, target, confirmed=True), done,
                 "Rechazando " + kind)

    def undo_flow(_btn) -> None:
        if not confirm("¿Deshacer el último ajuste?",
                       "Se revertirá el último ajuste aplicado del Kernel Engine."):
            set_status("Deshacer cancelado por el usuario")
            return

        def done(res):
            rb = res.get("rolled_back") if isinstance(res, dict) else None
            if rb:
                set_status("Deshecho: " + str(rb.get("kind", ""))
                           + " (ciclo " + str(rb.get("cycle", "?")) + ")")
            else:
                set_status("Deshacer: " + str(res.get("state", res) if isinstance(res, dict) else res))
        run_slow(lambda: panel.undo_last(confirmed=True), done, "Desheciendo último ajuste")

    def cycle_flow(_btn) -> None:
        def done(res):
            cycle = res.get("cycle", {}) if isinstance(res, dict) else {}
            set_status("Ciclo: aplicados " + str(len(cycle.get("applied", [])))
                       + ", revertidos " + str(len(cycle.get("rolled_back", []))))
        run_slow(lambda: panel.run_cycle(), done, "Ejecutando ciclo de diagnóstico")

    def history_flow(_btn) -> None:
        stack.set_visible_child_name("nke_history")

        def done(res):
            update_history(res.get("events", []) if isinstance(res, dict) else [])
        run_slow(lambda: panel.history(), done, "Cargando historial")

    cycle_btn.connect("clicked", cycle_flow)
    undo_btn.connect("clicked", undo_flow)
    history_btn.connect("clicked", history_flow)

    def update_nke(snap: Dict[str, Any]) -> None:
        fp = snap.get("footprint") or {}
        avg = fp.get("avg_cycle_ms")
        avg_txt = "sin datos" if avg is None else str(avg) + " ms"
        nke_header.set_text("Kernel: " + str(snap.get("kernel_release"))
                            + " | Ciclos: " + str(snap.get("cycles"))
                            + " | Ciclo medio: " + avg_txt
                            + " | Intervalo de monitorización: "
                            + str(fp.get("monitor_interval_s")) + " s")
        pol = snap.get("policies") or {}
        sin_impl = [k for k, v in pol.items() if not v.get("implemented", True)]
        nke_pol_label.set_text("Catálogo: " + str(len(pol))
                               + " acciones; sin implementación segura: "
                               + (", ".join(sin_impl) if sin_impl else "ninguna"))
        for child in nke_pending_box.get_children():
            nke_pending_box.remove(child)
        pending = snap.get("pending", [])
        if not pending:
            empty = Gtk.Label(label="Sin propuestas supervisadas pendientes", xalign=0)
            empty.get_style_context().add_class("dimmed")
            nke_pending_box.pack_start(empty, False, False, 0)
        for p in pending:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            text = (p["kind"] + " en " + str(p["target"])
                    + " [" + str(p["category_label"]) + "]"
                    + (": " + p["impact"] if p.get("impact") else ""))
            row.pack_start(Gtk.Label(label=text, xalign=0), False, False, 0)
            if p.get("implemented"):
                b_ok = Gtk.Button(label="Aprobar")
                b_ok.connect("clicked", approve_flow, p)
                b_no = Gtk.Button(label="Rechazar")
                b_no.connect("clicked", reject_flow, p)
                row.pack_start(b_ok, False, False, 0)
                row.pack_start(b_no, False, False, 0)
            else:
                na = Gtk.Label(label="No disponible: sin implementación segura", xalign=0)
                na.get_style_context().add_class("dimmed")
                row.pack_start(na, False, False, 0)
            nke_pending_box.pack_start(row, False, False, 0)
        nke_pending_box.show_all()
        mods = snap.get("modifications") or {}
        by = mods.get("by_state") or {}
        nke_mods_label.set_text("Ajustes registrados: " + str(mods.get("total", 0))
                                + " (aplicados: " + str(by.get("applied", 0))
                                + ", revertidos: " + str(by.get("reverted", 0))
                                + ", fallidos: " + str(by.get("failed", 0)) + ")")

    # --- Historial NKE -------------------------------------------------------
    hist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, border_width=12)
    hist_scroll = Gtk.ScrolledWindow()
    hist_scroll.add(hist_box)
    stack.add_titled(hist_scroll, "nke_history", "Historial NKE")

    def update_history(events) -> None:
        for child in hist_box.get_children():
            hist_box.remove(child)
        if not events:
            empty = Gtk.Label(label="Sin eventos registrados", xalign=0)
            hist_box.pack_start(empty, False, False, 0)
        for e in events[-50:]:
            try:
                line = json.dumps(e, ensure_ascii=False, sort_keys=True)[:200]
            except (TypeError, ValueError):
                line = str(e)[:200]
            hist_box.pack_start(Gtk.Label(label=line, xalign=0), False, False, 0)
        hist_box.show_all()

    # --- Hub -----------------------------------------------------------------
    hub_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, border_width=12)
    hub_scroll = Gtk.ScrolledWindow()
    hub_scroll.add(hub_box)
    stack.add_titled(hub_scroll, "hub", "Hub")

    def update_hub(res: Dict[str, Any]) -> None:
        for child in hub_box.get_children():
            hub_box.remove(child)
        agents = res.get("agents", []) if isinstance(res, dict) else []
        if not agents:
            empty = Gtk.Label(label="Sin agentes registrados", xalign=0)
            hub_box.pack_start(empty, False, False, 0)
        for a in agents:
            hub_box.pack_start(Gtk.Label(label=str(a.get("name")) + " ("
                                         + str(a.get("kind")) + "): "
                                         + str(a.get("status")), xalign=0),
                               False, False, 0)
        hub_box.show_all()

    # --- Sistema -------------------------------------------------------------
    sys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, border_width=12)
    sys_scroll = Gtk.ScrolledWindow()
    sys_scroll.add(sys_box)
    stack.add_titled(sys_scroll, "system_center", "Sistema")

    def update_system(sections: Dict[str, Any]) -> None:
        for child in sys_box.get_children():
            sys_box.remove(child)
        for name, section in sections.items():
            title = Gtk.Label(label=section.get("label", name), xalign=0)
            title.get_style_context().add_class("accent")
            sys_box.pack_start(title, False, False, 0)
            for entry in section.get("entries", []):
                state = entry.get("state", "error")
                line = "  " + str(entry.get("label", "")) + " [" + STATE_LABELS.get(state, state) + "]"
                sys_box.pack_start(Gtk.Label(label=line, xalign=0), False, False, 0)
        sys_box.show_all()

    header.set_custom_title(stack_switcher)
    outer.pack_start(stack, True, True, 0)
    outer.pack_start(status, False, False, 0)
    win.add(outer)

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
            theme_css = GTK_CSS.format(accent=ACCENT_DEFAULT)
    try:
        provider.load_from_data(theme_css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            win.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    except GLib.Error as exc:
        set_status("CSS del tema no válido, se usa el tema base: " + str(exc))

    # Instantáneas del panel: producción en hilo de trabajo y consumo en el
    # hilo gráfico. Un temporizador de GLib agenda el refresco periódico.
    poller = Poller(producer=lambda: {
        "dashboard": app.dashboard.snapshot(),
        "modes": app.mode_center.overview(),
        "nke": panel.snapshot(),
        "hub": app.hub.agents(app.registry),
        "system": app.system_center.sections(),
    }, interval_ms=REFRESH_INTERVAL_MS)
    poller.listeners.append(lambda snap: (
        update_dashboard(snap.get("dashboard", {})),
        update_modes(snap.get("modes", {})),
        update_nke(snap.get("nke", {})),
        update_hub(snap.get("hub", {})),
        update_system(snap.get("system", {})),
    ))

    def poll_tick() -> bool:
        if runner.pending == 0:
            runner.submit(poller.producer, on_done=poller.consume,
                          on_error=lambda exc: poller.consume(
                              {"state": "error", "message": str(exc)}))
        return True

    GLib.timeout_add(REFRESH_INTERVAL_MS, poll_tick)
    GLib.idle_add(once(poll_tick))

    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0
