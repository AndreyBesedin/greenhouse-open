"""Give the epochs a run store kept before P18.2 their usage reports, once.

    python -m greenhouse_sim.usage_reports ~/.local/state/greenhouse-sim/runs

A list of such epochs walks each of them, and a list writes nothing, so that it
stays as slow as it was until this is run. Only reports are written, each in the
way the store writes everything: no run id, digest or position moves. An epoch
with a report, or being worked, is left alone, and running this again changes
nothing. What no worker measured, its CPU time and peak memory, stays absent. It
may run beside a server. It says how many epochs it wrote and skipped, and why
each of those that failed did; the exit code is 1 if any did
(`greenhouse_sim.services.usage_reports`).
"""

import argparse
import sys
from pathlib import Path

from greenhouse_sim.services.run_store import FolderStore
from greenhouse_sim.services.usage_reports import report_missing


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m greenhouse_sim.usage_reports",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("folder", type=Path, help="the run store's folder")
    parsed = parser.parse_args(arguments)
    if not parsed.folder.is_dir():
        parser.error(f"no folder {parsed.folder}")
    done = report_missing(FolderStore(parsed.folder))
    print(
        f"{done.written} written, {done.had_report} skipped with a report, "
        f"{done.being_worked} skipped as being worked, {len(done.failed)} failed"
    )
    for failed in done.failed:
        print(f"failed {failed.where}: {failed.reason}")
    return 1 if done.failed else 0


if __name__ == "__main__":
    sys.exit(main())
