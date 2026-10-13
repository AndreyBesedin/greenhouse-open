"""Wall-clock time spent in the named parts of a run, for its benchmark
(P09.8): the house's air, the plants' light and the plants' days, as a run
works them out. A run given none times nothing."""

import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager


class Stopwatch:
    """Seconds spent in each part timed, added up over every time it ran."""

    def __init__(self) -> None:
        self.seconds: defaultdict[str, float] = defaultdict(float)

    @contextmanager
    def timing(self, part: str) -> Iterator[None]:
        """Adds the time spent within the block to `part`'s."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.seconds[part] += time.perf_counter() - started


@contextmanager
def timed(watch: Stopwatch | None, part: str) -> Iterator[None]:
    """Times the block as `part` on `watch`, if there is one."""
    if watch is None:
        yield
        return
    with watch.timing(part):
        yield
