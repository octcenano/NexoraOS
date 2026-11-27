#!/usr/bin/env python3
"""nexora-ebpf-loader: carga, consume y consulta los programas eBPF de NexoraOS."""
import argparse
import subprocess
import sys

PIN = "/sys/fs/bpf/nexora"


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def load_all():
    r = sh(["bpftool", "prog", "loadall", "sentinel.bpf.o", PIN + "/probes"])
    print(r.stdout or r.stderr)


def consume():
    if not subprocess.run(["test", "-d", PIN], capture_output=True).returncode == 0:
        print("sin programas anclados en %s (modo degradado: /proc)" % PIN)
        return 1
    r = sh(["bpftool", "map", "dump", "pinned", PIN + "/events"])
    print(r.stdout[:4000] or "(sin eventos)")
    return 0


def status():
    r = sh(["bpftool", "prog", "list"])
    lines = [l for l in r.stdout.splitlines() if "nexora" in l.lower() or "bpf" in l.lower()]
    print("\n".join(lines[:10]) or "sin programas eBPF")


def main():
    parser = argparse.ArgumentParser(prog="nexora-ebpf-loader")
    parser.add_argument("cmd", choices=["load", "consume", "status"])
    args = parser.parse_args()
    if args.cmd == "load":
        load_all()
    elif args.cmd == "consume":
        return consume()
    else:
        status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
