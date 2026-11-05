"""What this process has used of its machine (decision 0067): the figures a
worker, a process with one epoch to work out, reports beside that epoch. They
are a machine's, and no trajectory depends on them.
"""

import os
import resource
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

KIBIBYTE: Final = 1024
_PROCESS_STATUS: Final = Path("/proc/self/status")
# What wall time this process counts from: as a worker imports this, which is before it
# has done anything of its own.
_BEGAN: Final = time.monotonic()
_HIGH_WATER_LINE: Final = "VmHWM:"
# How far below the API a worker runs (decision 0067): on a machine it fills, the
# API and a viewer beside it are given a core first, and it the rest.
WORKER_NICENESS: Final = 10


@dataclass(frozen=True)
class ProcessUse:
    """What a process has used since it began: seconds of a core, in all its
    threads, the most memory it has held at once, and seconds of the wall's clock, in
    which a machine asleep counts for nothing."""

    cpu_s: float
    peak_memory_bytes: int
    wall_s: float = 0.0


def maxrss_bytes(maxrss: int, platform: str = sys.platform) -> int:
    """`ru_maxrss` in bytes: macOS gives bytes, and Linux and others KiB."""
    return maxrss if platform == "darwin" else maxrss * KIBIBYTE


def high_water_bytes(status: str) -> int | None:
    """The peak resident memory that Linux's `/proc/self/status` gives, in KiB,
    in bytes; none if the text does not say."""
    for line in status.splitlines():
        if line.startswith(_HIGH_WATER_LINE):
            return int(line.split()[1]) * KIBIBYTE
    return None


def peak_memory_bytes() -> int:
    """The most memory this process has held. Linux first, from `/proc`:
    `ru_maxrss` outlives an `exec` there, so that a worker would be told the
    peak of the server that started it, whereas this counts from its own."""
    try:
        peak = high_water_bytes(_PROCESS_STATUS.read_text())
    except OSError:
        peak = None
    if peak is not None:
        return peak
    return maxrss_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def this_process() -> ProcessUse:
    return ProcessUse(time.process_time(), peak_memory_bytes(), time.monotonic() - _BEGAN)


def machine_memory_bytes() -> int:
    """How much memory this machine has."""
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def lower_priority() -> None:
    """Makes this process, a worker, give way to the machine's other work."""
    os.nice(WORKER_NICENESS)
