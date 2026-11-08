"""P18's final scenario, what of it holds without a person looking
(`docs/roadmap/p18-resources-and-deployment.md`), at a small scale: a batch asked for
past the room for runs waiting, the rest refused in words; a disk at its floor, which
refuses the next run; and a server closed mid-batch, after which what waited still
waits and what was computed is `interrupted`, and is let in again when resumed. Each
simulator differs from the one before it in its limits alone, on the same store, and
is asked through the routes alone."""

import sys
import time
from collections import Counter
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes import respond
from greenhouse_sim.services import scheduler
from greenhouse_sim.services.limits import Limits, in_words
from greenhouse_sim.services.run_store import FolderStore, stored_runs
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

import workers_support

SHORT: Final = workers_support.SHORT
WORKERS: Final = 2
WAITING: Final = 20
ASKED: Final = 30
BATCH: Final = Limits(workers=WORKERS, waiting_runs=WAITING)
WAIT_S: Final = 60.0
# No word of a refusal is a name of the file's.
FIELD_NAMES: Final = tuple(Limits.model_fields)


@pytest.fixture
def held_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workers that hold their places and compute nothing, so that what waits does
    not depend on how fast a run goes."""
    monkeypatch.setattr(scheduler, "work", workers_support.holds_its_place)


def _until(holds: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not holds():
        if time.monotonic() > deadline:
            raise AssertionError(f"waited {WAIT_S} s for {what}")
        time.sleep(0.02)


def _simulator(store: Path, limits: Limits) -> Simulator:
    made = workers_support.short_simulator()
    made.runs = FolderStore(store)
    made.limits = limits
    return made


def _ask(simulator: Simulator, seed: int) -> Response:
    return respond(simulator, "POST", f"/api/scenarios/{SHORT}/runs?seed={seed}")


def _statuses(simulator: Simulator) -> Counter[str]:
    listed = respond(simulator, "GET", "/api/runs")
    assert listed.status == HTTPStatus.OK
    assert isinstance(listed.body, list)
    return Counter(str(run["status"]) for run in listed.body if isinstance(run, dict))


def _in_words(refusal: str, *figures: str) -> None:
    assert all(figure in refusal for figure in figures), refusal
    assert not any(name in refusal for name in FIELD_NAMES), refusal


def _in_store(store: Path) -> list[str]:
    return sorted(str(path.relative_to(store)) for path in store.rglob("*") if path.is_file())


def test_a_batch_past_the_room_for_runs_waiting_is_refused_in_words_and_the_rest_wait(
    tmp_path: Path, held_workers: None
) -> None:
    with _simulator(tmp_path, BATCH) as simulator:
        answers = [_ask(simulator, seed) for seed in range(1, ASKED + 1)]
        room = respond(simulator, "GET", "/api/room").body
        statuses = _statuses(simulator)

    # The two a free worker takes at once do not wait, and so are not refused.
    let_in = [answer for answer in answers if answer.status == HTTPStatus.OK]
    refused = [answer for answer in answers if answer.status != HTTPStatus.OK]
    assert len(let_in) == WORKERS + WAITING
    assert {answer.status for answer in refused} == {HTTPStatus.CONFLICT}
    said = {str(answer.body["error"]) for answer in refused if isinstance(answer.body, dict)}
    assert len(refused) == ASKED - WORKERS - WAITING and len(said) == 1
    (refusal,) = said
    _in_words(refusal, f"{WAITING} runs waiting", f"lets {WAITING} runs wait", "raise that limit")
    assert isinstance(room, dict)
    assert (room["workers_busy"], room["runs_waiting"], room["refusal"]) == (
        WORKERS,
        WAITING,
        refusal,
    )
    # Nothing of a run refused is kept: the list holds those let in, and no more.
    assert sum(statuses.values()) == WORKERS + WAITING


def test_a_disk_at_its_floor_refuses_the_next_run_in_words_with_nothing_written(
    tmp_path: Path, held_workers: None
) -> None:
    with _simulator(tmp_path, BATCH) as simulator:
        assert _ask(simulator, 1).status == HTTPStatus.OK
    written = _in_store(tmp_path)

    # The floor raised above what the disk has free, rather than the disk filled to it.
    free = FolderStore(tmp_path).free_bytes()
    assert free is not None
    floor = free + 10**9
    with _simulator(tmp_path, BATCH.model_copy(update={"free_disk_bytes": floor})) as simulator:
        answered = _ask(simulator, 2)
        room = respond(simulator, "GET", "/api/room").body

    assert answered.status == HTTPStatus.CONFLICT and isinstance(answered.body, dict)
    refusal = str(answered.body["error"])
    said = ("the disk of the run store has", f"{in_words(floor)} free", "lower that limit")
    _in_words(refusal, *said)
    # The room says it in the same words, the disk's free bytes read again.
    assert isinstance(room, dict)
    _in_words(str(room["refusal"]), *said)
    assert _in_store(tmp_path) == written


def test_a_server_closed_mid_batch_leaves_what_waits_waiting_and_what_ran_resumable(
    tmp_path: Path, held_workers: None
) -> None:
    with _simulator(tmp_path, BATCH) as first:
        asked = [_ask(first, seed) for seed in range(1, WORKERS + WAITING + 1)]
        assert {answer.status for answer in asked} == {HTTPStatus.OK}
        _until(lambda: len(scheduler.of(first).workers()) == WORKERS, "both workers")
    left = Counter(str(run.status) for run in stored_runs(FolderStore(tmp_path)))
    assert left == {"queued": WAITING, "interrupted": WORKERS}

    # A server started on the store, as one is after a restart, knows the scenario from it.
    with Simulator(runs=FolderStore(tmp_path), limits=BATCH) as second:
        _until(lambda: len(scheduler.of(second).workers()) == WORKERS, "the queue's first two")
        room = respond(second, "GET", "/api/room").body
        assert isinstance(room, dict)
        assert (room["workers_busy"], room["runs_waiting"]) == (WORKERS, WAITING - WORKERS)
        listed = respond(second, "GET", "/api/runs").body
        assert isinstance(listed, list)
        stopped = [
            run for run in listed if isinstance(run, dict) and run["status"] == "interrupted"
        ]
        assert len(stopped) == WORKERS

        resumed = [
            respond(second, "POST", f"/api/runs/{run['run_id']}/epochs/{run['epoch']}/resume")
            for run in stopped
        ]

        assert {answer.status for answer in resumed} == {HTTPStatus.OK}
        assert all(isinstance(a.body, dict) and a.body["status"] == "queued" for a in resumed)
        # They wait again where the restart had left room, which they fill.
        full = respond(second, "GET", "/api/room").body
        assert isinstance(full, dict)
        assert (full["workers_busy"], full["runs_waiting"]) == (WORKERS, WAITING)
        _in_words(str(full["refusal"]), f"{WAITING} runs waiting")
