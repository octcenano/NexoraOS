"""CLI / plano de control de NEXORA OS."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from nexora import __version__
from nexora.agents.meteorology import OpenMeteoProvider, SimulatedWeatherProvider, WeatherProviderError
from nexora.core.ai_engine import engine_from_config
from nexora.core.config import ConfigError, load_config
from nexora.core.profiles import calculate_hybrid_profile, detect_hardware
from nexora.core.registry import ModeRegistry
from nexora.diagnostics.health import health_report
from nexora.ui.dashboard import NexoraDashboard
from nexora.watchdog import watchdog_from_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexora",
        description="NEXORA OS: plano de control",
        epilog="Ejemplos: nexora health · nexora weather Madrid --live · nexora audit",
    )
    parser.add_argument("--version", action="version", version=f"NEXORA OS {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("modes", help="Lista los modos registrados con su estado real")

    p = sub.add_parser("profile", help="Calcula el perfil híbrido")
    p.add_argument("--profile", choices=["auto", "compact", "balanced", "expanded", "manual"], default="auto")
    p.add_argument("--cpu-cores", type=int, help="Por defecto, detectado del sistema")
    p.add_argument("--ram-gb", type=float, help="Por defecto, detectado del sistema")

    d = sub.add_parser("dashboard", help="Muestra el estado del dashboard")
    d.add_argument("--mode", help="Modo activo inicial")
    d.add_argument("--json", action="store_true", help="Salida JSON (el modelo que consumirá la GUI)")

    h = sub.add_parser("health", help="Diagnóstico del sistema")
    h.add_argument("--json", action="store_true")

    w = sub.add_parser("weather", help="Observación meteorológica")
    w.add_argument("location")
    w.add_argument("--live", action="store_true", help="Consulta Open-Meteo (envía la ubicación a un servicio externo)")

    a = sub.add_parser("ask", help="Consulta al motor IA local desde un modo")
    a.add_argument("prompt")
    a.add_argument("--mode", default="forge")

    s = sub.add_parser("status", help="Supervisión del core (watchdog, una pasada)")
    s.add_argument("--json", action="store_true")

    u = sub.add_parser("audit", help="Auditoría defensiva de solo lectura (modo Security)")
    u.add_argument("--json", action="store_true")
    return parser


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
    registry = ModeRegistry()
    agent = registry.create_agent("meteorology", provider=provider)
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        print(f"NEXORA OS Control Plane CLI v{__version__}")
        print("Usa --help para ver los comandos disponibles.")
        return 0

    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    if args.command == "modes":
        print(f"--- Modos de NEXORA OS (v{__version__}) ---")
        for mode, data in ModeRegistry().get_modes().items():
            estado = {"stub": "solo registrado", "basic": "funcionalidad básica"}.get(data.get("status", "stub"),
                                                                                       data.get("status", "stub"))
            print(f"- {mode.upper()}: {data['description']} [{estado}]")
        return 0

    if args.command == "profile":
        try:
            return _cmd_profile(args)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.command == "dashboard":
        engine = engine_from_config(cfg)
        try:
            dash = NexoraDashboard(engine=engine, initial_mode=args.mode or "forge")
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(dash.render_layout(), ensure_ascii=False, indent=2) if args.json else dash.render_text())
        return 0

    if args.command == "health":
        report = health_report(cfg)
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
        return _cmd_weather(args, cfg)

    if args.command == "ask":
        registry = ModeRegistry()
        if not registry.is_valid(args.mode):
            print(f"Error: modo desconocido: {args.mode}", file=sys.stderr)
            return 2
        engine = engine_from_config(cfg)
        if engine.simulated:
            print("Aviso: motor IA simulado; configura ai_engine.backend para usar un modelo local.", file=sys.stderr)
        print(registry.create_agent(args.mode, engine=engine).process_prompt(args.prompt))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
