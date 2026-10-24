"""Tests that run OpenFOAM (marked `cfd`) run only when asked for, with
`pytest -m cfd`, and are skipped where OpenFOAM cannot run. Without OpenFOAM
installed they pull its container the first time, about 2 GB, so neither the
canonical checks nor the pre-push pass run them.

`finishes_beside_held` tells whether something gets on while another thread
holds a lock, as a request working a run on holds the run's; `held_in_a_day`
keeps a live run working a day out until the test lets it finish.

A test that answers requests, plays runs back, or asks a service that
reads or keeps runs, asks for `simulator` (decision 0048): one a module's
tests share, with the scenarios' opening days kept as the API's server keeps
them, closed after the module. What it keeps is its own.

A test that needs what the services keep forgotten asks for it here, never
of a store itself (W9): `afresh` (or `afresh_module`, for a module's
fixtures) has the module's simulator forget everything it keeps, before the
test and whenever it calls it, and keep the scenarios' opening days again
after it; `no_playbacks` stops every run the module's simulator plays back,
and leaves the runs kept."""

import gzip
import json
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import pytest

from greenhouse_sim.cfd import runner
from greenhouse_sim.scenarios.manifest_files import opening_file
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.checkpoints import load_openings
from greenhouse_sim.services.live import LiveFrame, LiveRun
from greenhouse_sim.services.playback import stop_playbacks
from greenhouse_sim.services.simulator import Simulator


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    asked = "cfd" in (config.getoption("markexpr") or "")
    unasked = pytest.mark.skip(reason="runs OpenFOAM: only with -m cfd")
    unavailable = pytest.mark.skip(reason="OpenFOAM is not installed, and Docker is not running")
    can_run: bool | None = None
    for item in items:
        if item.get_closest_marker("cfd") is None:
            continue
        if not asked:
            item.add_marker(unasked)
            continue
        if can_run is None:
            can_run = runner.available()
        if not can_run:
            item.add_marker(unavailable)


# How long an action beside a held lock may take before it counts as
# waiting for the lock.
_WAIT_S = 2.0
# How long a live run held in a day waits to be let finish, at most.
_HELD_DAY_S = 5.0

type _Held = Callable[[LiveRun, threading.Event], threading.Event]


@pytest.fixture
def held_in_a_day(monkeypatch: pytest.MonkeyPatch) -> _Held:
    """Makes a live run's next day last until `release` is set, its pacing
    thread holding the run meanwhile, as one working an expensive day out
    does; answers the event set once that day has begun."""

    def hold(run: LiveRun, release: threading.Event) -> threading.Event:
        begun = threading.Event()
        advance = run.advance

        def held() -> LiveFrame:
            begun.set()
            release.wait(_HELD_DAY_S)
            return advance()

        monkeypatch.setattr(run, "advance", held)
        return begun

    return hold


type _Beside = Callable[[AbstractContextManager[bool], Callable[[], object]], bool]


@pytest.fixture
def finishes_beside_held() -> _Beside:
    def finishes(lock: AbstractContextManager[bool], action: Callable[[], object]) -> bool:
        taken, release = threading.Event(), threading.Event()

        def hold() -> None:
            with lock:
                taken.set()
                release.wait()

        holder = threading.Thread(target=hold, daemon=True)
        holder.start()
        taken.wait()
        worker = threading.Thread(target=action, daemon=True)
        worker.start()
        worker.join(timeout=_WAIT_S)
        finished = not worker.is_alive()
        release.set()
        holder.join()
        worker.join()
        return finished

    return finishes


@contextmanager
def _clean_slate(simulator: Simulator) -> Iterator[Callable[[], None]]:
    simulator.forget()
    try:
        yield simulator.forget
    finally:
        simulator.forget()
        load_openings(simulator)


@pytest.fixture
def afresh(simulator: Simulator) -> Iterator[Callable[[], None]]:
    with _clean_slate(simulator) as forget:
        yield forget


@pytest.fixture(scope="module")
def afresh_module(simulator: Simulator) -> Iterator[Callable[[], None]]:
    with _clean_slate(simulator) as forget:
        yield forget


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    # With the scenarios' opening days kept, as the API's server keeps them.
    with Simulator() as made:
        load_openings(made)
        yield made


@pytest.fixture
def no_playbacks(simulator: Simulator) -> Iterator[Callable[[], None]]:
    def stop() -> None:
        stop_playbacks(simulator)

    stop()
    try:
        yield stop
    finally:
        stop()


@pytest.fixture
def written_in_format_3() -> Callable[[bool], dict[str, Any]]:
    """The reference greenhouse's kept opening day, its run's, or its run's
    with everything off, as checkpoint format 3 wrote it: its run's plan as
    its commands, daily commands and target changes. Made from the
    checkpoint as it is kept, so that it holds whatever format the kept
    files are written in again."""

    def written(all_off: bool = False) -> dict[str, Any]:
        kept = checkpoints.read_checkpoint(
            json.loads(gzip.decompress(opening_file("reference_greenhouse", all_off).read_bytes()))
        )
        plan = kept.plan
        document = {
            name: value
            for name, value in json.loads(kept.model_dump_json()).items()
            if name not in ("plan", "models")
        }
        # Its plants and the days they lived beside its run, as formats 3
        # and 4 kept them, not as its organ crop's state.
        return (
            document
            | kept.crop.model_dump(mode="json")
            | {
                "checkpoint_format": checkpoints.WITH_COMMANDS,
                "commands": [list(each) for each in plan.commanded()],
                "daily": None
                if plan.daily is None
                else [list(each) for each in plan.daily_commanded() or ()],
                "targets": [list(each) for each in plan.targeted()],
            }
        )

    return written
