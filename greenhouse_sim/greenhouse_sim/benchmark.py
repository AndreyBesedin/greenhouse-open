"""The simulator's benchmark on the reference scenario (P09.8): its costs
(`greenhouse_sim.services.benchmark`), with the machine it ran on and the
process's peak memory, as a JSON report, compared with the one kept in the
repository, `greenhouse_sim/benchmarks/simulator.json`, when the simulator
runs from a checkout of it, or with the one `--report` names. From
`greenhouse_sim/`:

    python -m greenhouse_sim.benchmark              # the whole season, about 4 min
    python -m greenhouse_sim.benchmark --days 10    # its first ten days
    python -m greenhouse_sim.benchmark --record     # and keep the report

It is a record, not a gate: it never fails on the numbers. The renderer's
side is measured in the browser, on a graphics card (`npm run bench` in
`web/`, decision 0015).
"""

import argparse
import datetime
import json
import os
import platform
import resource
import subprocess
import sys
from pathlib import Path
from typing import Final

from greenhouse_sim.scenarios.manifest_files import FIRST_SCENARIO
from greenhouse_sim.services.benchmark import costs_json, simulator_costs
from greenhouse_sim.services.simulator import Simulator

# The report kept in the repository, beside the package's source: found only
# when the simulator runs from a checkout, not installed as a package.
CHECKOUT_REPORT: Final = Path(__file__).resolve().parents[1] / "benchmarks" / "simulator.json"
GIBIBYTE: Final = 1024**3
MEBIBYTE: Final = 1024**2
KIBIBYTE: Final = 1024
# What the CPU is called, where the system says.
CPU_NAME_TIMEOUT_S: Final = 5.0


def _cpu_name() -> str:
    if sys.platform == "darwin":
        try:
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=CPU_NAME_TIMEOUT_S,
                check=True,
            ).stdout.strip()
        except OSError, subprocess.SubprocessError:
            pass
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    return platform.processor() or "unknown"


def machine() -> dict[str, object]:
    """The machine the benchmark ran on, and the Python that ran it."""
    memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    return {
        "platform": f"{sys.platform} {platform.machine()}",
        "cpu": _cpu_name(),
        "cores": os.cpu_count(),
        "memory_gib": round(memory / GIBIBYTE),
        "python": platform.python_version(),
    }


def peak_memory_mib() -> float:
    """The most memory the process has held: bytes on macOS, KiB elsewhere."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    scale = 1 if sys.platform == "darwin" else KIBIBYTE
    return round(peak * scale / MEBIBYTE, 1)


def report(
    simulator: Simulator, days: int | None = None, scenario_id: str = FIRST_SCENARIO
) -> dict[str, object]:
    """The benchmark's report: when, on what, and what it measured."""
    costs = json.loads(costs_json(simulator_costs(simulator, scenario_id, days)))
    return {
        "recorded": datetime.date.today().isoformat(),
        "machine": machine(),
        **costs,
        "peak_memory_mib": peak_memory_mib(),
    }


def compared(latest: dict[str, object], kept: dict[str, object] | None) -> str:
    """The latest report beside the kept one, part by part."""
    per_day = latest["per_day"]
    kept_day = kept.get("per_day") if kept is not None else None
    assert isinstance(per_day, dict)
    lines = [f"{latest['scenario_id']}, {latest['days']} days on {latest['machine']}"]
    lines.append("seconds per simulated day   now  (kept)")
    for part, value in per_day.items():
        then = kept_day.get(part) if isinstance(kept_day, dict) else None
        lines.append(f"  {part:<24}{value:>6}  ({'—' if then is None else then})")
    for measure in ("season_s", "cell_by_cell_hour_s", "frame_scene_s", "peak_memory_mib"):
        then = kept.get(measure) if kept is not None else None
        lines.append(f"{measure:<28}{latest[measure]:>6}  ({'—' if then is None else then})")
    lines.append(f"next bottleneck: {latest['bottleneck']}")
    return "\n".join(lines)


def kept_report() -> Path | None:
    """Where the kept report lies: the repository's, when the simulator runs
    from a checkout of it."""
    return CHECKOUT_REPORT if CHECKOUT_REPORT.parent.is_dir() else None


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--days", type=int, help="the days measured, by default the season")
    parser.add_argument("--record", action="store_true", help="keep the report")
    parser.add_argument(
        "--report", type=Path, default=kept_report(), help="the kept report, to compare and keep"
    )
    parsed = parser.parse_args(arguments)
    if parsed.record and parsed.report is None:
        parser.error("no kept report here to keep it as: name one with --report")
    with Simulator() as simulator:
        latest = report(simulator, parsed.days)
    path: Path | None = parsed.report
    kept = json.loads(path.read_text()) if path is not None and path.exists() else None
    print(compared(latest, kept))
    if parsed.record and path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(latest, indent=2) + "\n")
        print("kept", path)


if __name__ == "__main__":
    main()
