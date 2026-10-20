"""Tests that run OpenFOAM (marked `cfd`) run only when asked for, with
`pytest -m cfd`, and are skipped where OpenFOAM cannot run. Without OpenFOAM
installed they pull its container the first time, about 2 GB, so neither the
canonical checks nor the pre-push pass run them.

`finishes_beside_held` tells whether something gets on while another thread
holds a lock, as a request working a run on holds the run's.

A test that needs what the services keep forgotten asks for it here, never
of a store itself (W9): `afresh` (or `afresh_module`, for a module's
fixtures) forgets everything every store keeps, before the test and
whenever it calls it, and keeps the scenarios' opening days again after it,
as the API keeps them as it starts; `no_playbacks` stops every run played
back, and leaves the runs kept."""

import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import pytest

from greenhouse_sim.cfd import runner
from greenhouse_sim.services.checkpoints import load_openings
from greenhouse_sim.services.playback import stop_playbacks
from greenhouse_sim.services.stores import forget_everything


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
def _clean_slate() -> Iterator[Callable[[], None]]:
    forget_everything()
    try:
        yield forget_everything
    finally:
        forget_everything()
        load_openings()


@pytest.fixture
def afresh() -> Iterator[Callable[[], None]]:
    with _clean_slate() as forget:
        yield forget


@pytest.fixture(scope="module")
def afresh_module() -> Iterator[Callable[[], None]]:
    with _clean_slate() as forget:
        yield forget


@pytest.fixture
def no_playbacks() -> Iterator[Callable[[], None]]:
    stop_playbacks()
    try:
        yield stop_playbacks
    finally:
        stop_playbacks()
