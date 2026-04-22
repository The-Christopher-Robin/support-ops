"""Drive the simulator against a running backend.

Usage:
    python scripts/run_simulation.py --tickets 1000 --duration 60
"""

from __future__ import annotations

import argparse
import asyncio

from rich.console import Console

from supportops.simulator.replay import SimConfig, run

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", type=int, default=1000)
    parser.add_argument("--duration", type=int, default=60, help="seconds")
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()

    cfg = SimConfig(
        tickets=args.tickets,
        duration_seconds=args.duration,
        backend_url=args.backend,
        concurrency=args.concurrency,
    )
    console.print(
        f"Sending [bold]{cfg.tickets}[/bold] tickets at {cfg.backend_url} over "
        f"{cfg.duration_seconds}s with concurrency {cfg.concurrency}"
    )
    result = asyncio.run(run(cfg))
    console.print(f"[green]done[/green] — {result}")


if __name__ == "__main__":
    main()
