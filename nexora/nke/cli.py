"""CLI dedicada de NKE (nexora-nke): modo bucle para systemd y diagnóstico.

Separada de la CLI principal para que la unidad systemd no dependa de la
configuración de usuario de nexora. Solo lectura salvo las acciones de
categoría A (reversibles y de bajo riesgo), que es el contrato de NKE.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from nexora.nke.engine import NKEngine


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="nexora-nke", description="Nexora Kernel Engine")
    parser.add_argument("--loop", type=float, metavar="SEG", help="Ejecuta en bucle (para systemd)")
    parser.add_argument("--max-loop-errors", type=int, default=3,
                        help="Errores consecutivos antes de salir (protección anti-bucle)")
    parser.add_argument("--once", action="store_true", help="Un único ciclo y sale")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    engine = NKEngine()

    if args.once:
        cycle = engine.run_cycle()
        print(json.dumps(cycle, ensure_ascii=False, indent=2) if args.json
              else f"NKE ciclo #{cycle['cycle']}: hallazgos={cycle['findings'] or 'ninguno'}, "
                   f"aplicadas={len(cycle['applied'])}, revertidas={len(cycle['rolled_back'])}")
        return 0

    if args.loop is None:
        print(json.dumps(engine.status(), ensure_ascii=False, indent=2) if args.json
              else "nexora-nke: usa --once, --loop SEG o --json")
        return 0

    # Modo bucle para systemd: mismo contrato anti-bucle que el watchdog.
    consecutive = 0
    while True:
        try:
            engine.run_cycle()
            consecutive = 0
        except Exception as exc:
            consecutive += 1
            print(f"[nke] error interno ({consecutive}/{args.max_loop_errors}): {exc}", file=sys.stderr)
            if consecutive >= max(args.max_loop_errors, 1):
                return 3
        engine.sleeper(max(args.loop, 5.0))


if __name__ == "__main__":
    raise SystemExit(main())
