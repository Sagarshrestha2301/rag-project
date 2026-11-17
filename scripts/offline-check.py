"""Prove from inside a process that it cannot reach the network.

Run this from the interpreter whose network the firewall rules are supposed to block.
Exit 0 means every attempt failed (the block is real); exit 1 means at least one
connection succeeded and the "offline" run that follows would prove nothing.

A Windows venv's `.venv\\Scripts\\python.exe` is a trampoline: it starts the base
interpreter named in `pyvenv.cfg` and that child is what opens sockets. Blocking only
the trampoline leaves the real interpreter unblocked, so both paths are checked here.

Usage:
    .venv\\Scripts\\python.exe scripts\\offline-check.py

Prints one line per target, then BLOCKED or REACHABLE.
"""

from __future__ import annotations

import socket
import sys

TARGETS = (("1.1.1.1", 443), ("8.8.8.8", 53))
TIMEOUT = 6.0


def main() -> int:
    reachable = []
    print(f"interpreter: {sys.executable}")
    print(f"base interpreter: {getattr(sys, '_base_executable', sys.executable)}")
    for host, port in TARGETS:
        sock = socket.socket()
        sock.settimeout(TIMEOUT)
        try:
            sock.connect((host, port))
            reachable.append(f"{host}:{port}")
            print(f"  {host}:{port} CONNECTED")
        except OSError as exc:
            print(f"  {host}:{port} blocked ({type(exc).__name__})")
        finally:
            sock.close()
    if reachable:
        print(f"REACHABLE: {', '.join(reachable)} - the network is not blocked for this process")
        return 1
    print("BLOCKED: no external connection succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
