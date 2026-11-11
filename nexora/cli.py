"""CLI / plano de control de NEXORA OS."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from nexora import __version__
from nexora.agents.meteorology import MeteorologyAgent, OpenMeteoProvider, SimulatedWeatherProvider, WeatherProviderError
from nexora.core.ai_engine import engine_from_config
from nexora.core.config import ConfigError, load_config
from nexora.core.profiles import calculate_hybrid_profile, detect_hardware
from nexora.core.registry import INTENSITY_LEVELS, ModeRegistry, SPECIALIST_AGENTS
from nexora.diagnostics.health import health_report
from nexora.ui.dashboard import NexoraDashboard
from nexora.watchdog import watchdog_from_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexora",
        description="NEXORA OS: plano de control",
        epilog="Ejemplos: nexora health · nexora modes · nexora mode gaming --intensity 3 · nexora desktop --json",
    )
    parser.add_argument("--version", action="version", version=f"NEXORA OS {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("modes", help="Lista los cinco modos oficiales con su estado real")

    p = sub.add_parser("profile", help="Calcula el perfil híbrido")
    p.add_argument("--profile", choices=["auto", "compact", "balanced", "expanded", "manual"], default="auto")
    p.add_argument("--cpu-cores", type=int, help="Por defecto, detectado del sistema")
    p.add_argument("--ram-gb", type=float, help="Por defecto, detectado del sistema")

    m = sub.add_parser("mode", help="Muestra o fija la intensidad de un modo oficial")
    m.add_argument("name", help="Modo oficial: gaming, hacking, office, stealth o forge")
    m.add_argument("--intensity", choices=list(INTENSITY_LEVELS), help="Nivel de intensidad a fijar")

    d = sub.add_parser("dashboard", help="Muestra el estado del dashboard")
    d.add_argument("--mode", help="Modo activo inicial")
    d.add_argument("--json", action="store_true", help="Salida JSON (el modelo que consumirá la GUI)")

    h = sub.add_parser("health", help="Diagnóstico del sistema")
    h.add_argument("--json", action="store_true")

    w = sub.add_parser("weather", help="Observación meteorológica (agente especializado)")
    w.add_argument("location")
    w.add_argument("--live", action="store_true", help="Consulta Open-Meteo (envía la ubicación a un servicio externo)")

    a = sub.add_parser("ask", help="Consulta al motor IA local desde un modo oficial")
    a.add_argument("prompt")
    a.add_argument("--mode", default="forge")

    s = sub.add_parser("status", help="Supervisión del core (watchdog, una pasada)")
    s.add_argument("--json", action="store_true")

    u = sub.add_parser("audit", help="Auditoría defensiva de solo lectura (seguridad transversal)")
    u.add_argument("--json", action="store_true")

    n = sub.add_parser("nke", help="Nexora Kernel Engine: estado, diagnóstico e historial")
    n.add_argument("action", nargs="?", choices=["status", "diagnose", "history"], default="status")
    n.add_argument("--json", action="store_true")

    dt = sub.add_parser("desktop", help="Nexora Desktop (XFCE + GTK3)")
    dt.add_argument("--json", action="store_true", help="Vuelca el modelo completo sin abrir ventana")
    dt.add_argument("--gtk", action="store_true", help="Arranca la ventana GTK3")
    return parser


def _cmd_mode(args) -> int:
    """Intensidad de un modo oficial: política real, sin efectos sobre el sistema."""
    registry = ModeRegistry()
    if not registry.is_valid(args.name):
        print(f"Error: modo desconocido: {args.name}", file=sys.stderr)
        print("Modos oficiales: " + ", ".join(registry.names()), file=sys.stderr)
        return 2
    if args.intensity:
        registry.set_intensity(args.name, args.intensity)
    level = args.intensity or registry.intensity(args.name)
    info = registry.intensity_policy(args.name, level)
    pol = info["policy"]
    print(f"Modo {args.name} · intensidad {level} ({pol.level})")
    print(f"  Efecto declarado: {info['effect']}")
    print(f"  Agentes concurrentes: {pol.concurrent_agents}")
    print(f"  RAM máxima para modelos: {pol.max_model_ram_gb} GB")
    print(f"  Peso de CPU en el reparto: {pol.cpu_weight}")
    print(f"  Ajuste agresivo: {'sí, exige compatibilidad comprobada y aprobación explícita' if pol.aggressive_tuning else 'no'}")
    print("  Nota: la intensidad es una política que consume el reparto de recursos")
    print("  (build_allocation); no modifica el sistema directamente.")
    return 0


def _cmd_profile(args) -> int:
    cpu, ram, note = args.cpu_cores, args.ram_gb, ""
    if cpu is None or ram is None:
        hw = detect_hardware()
        if hw is None:
            cpu, ram, note = 2, 4.0, "No se pudo detectar el hardware: se usa una base segura (2 núcleos, 4 GB)."
        else:
            cpu = hw.cpu_cores if cpu is None else cpu
            ram = hw.ram_gb if ram is None else ram
            note = f"Hardware detectado: núcleos={hw.cpu_cores}, RAM={hw.ram_gb} GB"
            if hw.gpus:
                note += f", GPU={'+'.join(hw.gpus)}"
            if hw.storage_free_gb is not None:
                note += f", almacenamiento libre={hw.storage_free_gb} GB"
            note += "."
    prof = calculate_hybrid_profile(args.profile, cpu, ram)
    if note:
        print(note)
    print(f"Perfil: {prof['name']} (estrategia: {prof['strategy']}, sugerido: {prof['suggested']})")
    print(f"Límites: {prof['limits']}")
    print(prof["note"])
    if "warning" in prof:
        print(f"AVISO: {prof['warning']}")
    return 0


def _cmd_weather(args, cfg) -> int:
    live = args.live or cfg["meteorology"]["provider"] == "open-meteo"
    provider = OpenMeteoProvider() if live else SimulatedWeatherProvider()
    agent = MeteorologyAgent(provider=provider)
    try:
        obs = agent.get_weather_observation(args.location)
    except (WeatherProviderError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    tag = " [SIMULADO]" if obs["simulated"] else ""
    print(f"{obs['resolved_location']}{tag}: {obs['temp_c']} °C, {obs['condition']}, "
          f"humedad {obs['humidity_pct']}%, viento {obs['wind_kmh']} km/h")
    print(f"Fuente: {obs['source']}. {obs['attribution']}")
    return 0


def _cmd_status(args) -> int:
    report = watchdog_from_config().run_once()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Supervisión NEXORA OS: {report['overall'].upper()}")
        for r in report["components"]:
            state = "OK" if r["healthy"] else ("RECUPERADO" if r.get("restarted") and r.get("recovered") else "FALLO")
            print(f"  [{state}] {r['component']}")
    return 0 if report["overall"] == "ok" else 1


def _cmd_audit(args) -> int:
    from nexora.agents.security import run_defensive_audit

    report = run_defensive_audit()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Auditoría defensiva (solo lectura): {report['overall'].upper()}")
        for c in report["checks"]:
            print(f"  [{c['status'].upper():<4}] {c['name']}: {c['detail']}")
    return 0 if report["overall"] != "fail" else 1


def _cmd_nke(args) -> int:
    """NKE desde la CLI: solo lectura en 'status'/'history'.

    'diagnose' ejecuta un ciclo completo del motor: las acciones de categoría
    A (reversibles y de bajo riesgo) pueden aplicarse; las B se listan como
    pendientes de aprobación y las C solo se documentan.
    """
    from nexora.nke.engine import NKEngine

    engine = NKEngine()
    if args.action == "status":
        report = engine.status()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        caps = report["capabilities"]
        print(f"Nexora Kernel Engine (kernel {caps['kernel_release']})")
        print(f"  PSI: {'sí' if caps['can_psi_monitoring'] else 'no disponible'} · "
              f"cgroups v2: {'sí' if caps['can_cgroup_limits'] else 'no disponible'}")
        print(f"  Ciclos ejecutados: {report['cycles']} · intervalo de sondeo: {report['monitor_interval_s']} s")
        print(f"  Historial: {report['history_summary'] or 'vacío'}")
        return 0

    if args.action == "diagnose":
        cycle = engine.run_cycle()
        if args.json:
            print(json.dumps(cycle, ensure_ascii=False, indent=2))
            return 0
        print(f"Ciclo NKE #{cycle['cycle']} ({cycle['duration_ms']} ms, sondeo cada {cycle['interval_s']} s)")
        print(f"  Hallazgos: {', '.join(cycle['findings']) or 'ninguno'}")
        print(f"  Acciones automáticas aplicadas: {cycle['applied'] or 'ninguna'}")
        if cycle["proposals_supervised"]:
            print("  Pendientes de aprobación (categoría B):")
            for pr in cycle["proposals_supervised"]:
                print(f"    - {pr['kind']} en {pr['target']}: {pr['why']}")
        if cycle["proposals_protected"]:
            print("  Protegidas (NKE no las ejecuta; requieren intervención manual):")
            for pr in cycle["proposals_protected"]:
                print(f"    - {pr['kind']} en {pr['target']}: {pr['why']}")
        if cycle["rolled_back"]:
            print(f"  Rollback automático por degradación: {cycle['rolled_back']}")
        return 0

    events = engine.history.events()
    if args.json:
        print(json.dumps(list(events), ensure_ascii=False, indent=2))
        return 0
    if not events:
        print("Historial NKE vacío (aún no se ha ejecutado ningún ciclo).")
        return 0
    for e in events:
        print(f"  [{e['kind']:<8}] {e['detail']}")
    return 0


def _cmd_desktop(args) -> int:
    """Nexora Desktop: modelo completo (--json) o ventana GTK3 (--gtk)."""
    from nexora.desktop import DesktopUnavailableError, NexoraDesktopApp

    engine = engine_from_config(cfg_global)
    try:
        app = NexoraDesktopApp(engine=engine)
        app.start()
    except PermissionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    try:
        if args.gtk:
            return app.run_gtk()
        print(json.dumps(app.layout(), ensure_ascii=False, indent=2))
        return 0
    except DesktopUnavailableError as exc:
        print(f"Nexora Desktop no disponible: {exc}", file=sys.stderr)
        return 4
    finally:
        if app.running:
            app.shutdown()


def main(argv: Optional[Sequence[str]] = None) -> int:
    global cfg_global
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        print(f"NEXORA OS Control Plane CLI v{__version__}")
        print("Usa --help para ver los comandos disponibles.")
        return 0

    if args.command == "nke":
        return _cmd_nke(args)

    if args.command == "mode":
        return _cmd_mode(args)

    try:
        cfg_global = load_config()
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    if args.command == "modes":
        print(f"--- Modos oficiales de NEXORA OS (v{__version__}) ---")
        registry = ModeRegistry()
        for mode, data in registry.get_modes().items():
            estado = {"stub": "solo registrado", "basic": "funcionalidad básica"}.get(data.get("status", "stub"),
                                                                                       data.get("status", "stub"))
            print(f"- {mode.upper()}: {data['description']} [{estado}] (intensidad por defecto: {registry.intensity(mode)})")
        print("--- Agentes especializados (no son modos) ---")
        for name, data in SPECIALIST_AGENTS.items():
            print(f"- {name}: {data['description']}")
        return 0

    if args.command == "profile":
        try:
            return _cmd_profile(args)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.command == "dashboard":
        engine = engine_from_config(cfg_global)
        try:
            dash = NexoraDashboard(engine=engine, initial_mode=args.mode or "forge")
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(dash.render_layout(), ensure_ascii=False, indent=2) if args.json else dash.render_text())
        return 0

    if args.command == "health":
        report = health_report(cfg_global)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"Estado general: {report['overall'].upper()}")
            for c in report["checks"]:
                print(f"  [{c['status']:<4}] {c['name']}: {c['detail']}")
            pending = [k for k, v in report["capabilities"].items() if v in ("planned_not_running", "not_installed", "not_implemented")]
            print(f"Pendiente (no implementado): {', '.join(pending)}")
        return 1 if report["overall"] == "fail" else 0

    if args.command == "status":
        return _cmd_status(args)

    if args.command == "audit":
        return _cmd_audit(args)

    if args.command == "weather":
        return _cmd_weather(args, cfg_global)

    if args.command == "desktop":
        return _cmd_desktop(args)

    if args.command == "ask":
        registry = ModeRegistry()
        if not registry.is_valid(args.mode):
            print(f"Error: modo desconocido: {args.mode}", file=sys.stderr)
            return 2
        engine = engine_from_config(cfg_global)
        if engine.simulated:
            print("Aviso: motor IA simulado; configura ai_engine.backend para usar un modelo local.", file=sys.stderr)
        print(registry.create_agent(args.mode, engine=engine).process_prompt(args.prompt))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
