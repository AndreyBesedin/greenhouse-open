"""What a simulator lets its runs use (P18.3, decision 0067): its limits, read from a
file and the server's options, with defaults for one machine; a run refused in words
when there is no room for it, with nothing written; and workers at a lower priority."""

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.api.server import _add_limits, _limits, create_server
from greenhouse_sim.services import resources, scheduler
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.limits import (
    DEFAULT_FREE_DISK_BYTES,
    DEFAULT_WAITING_RUNS,
    DEFAULT_WORKERS,
    GIGABYTE,
    NO_LIMIT,
    Limits,
    in_words,
    limits_given,
)
from greenhouse_sim.services.run_store import FolderStore, Status, held_bytes, stored_runs
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

import workers_support

SHORT: Final = workers_support.SHORT
LONG: Final = workers_support.LONG
WAIT_S: Final = 60.0
# No word of a refusal is a name of the file's.
FIELD_NAMES: Final = tuple(Limits.model_fields)


def _until(holds: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not holds():
        if time.monotonic() > deadline:
            raise AssertionError(f"waited {WAIT_S} s for {what}")
        time.sleep(0.02)


@pytest.fixture
def held_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workers that hold their places and compute nothing, so that a test of what
    waits does not depend on how fast a run goes."""
    monkeypatch.setattr(scheduler, "work", workers_support.holds_its_place)


def _simulator(store: Path, limits: Limits) -> Simulator:
    made = workers_support.short_simulator()
    made.runs = FolderStore(store)
    made.limits = limits
    return made


def _in_store(store: Path) -> list[str]:
    return sorted(str(path.relative_to(store)) for path in store.rglob("*") if path.is_file())


def _refused_in_words(refused: Conflict, *figures: str) -> None:
    assert all(figure in refused.message for figure in figures), refused.message
    assert not any(name in refused.message for name in FIELD_NAMES), refused.message


def test_the_defaults_are_those_of_the_decisions_table_for_one_machine() -> None:
    limits = Limits()

    assert limits.workers == DEFAULT_WORKERS == 2
    assert limits.waiting_runs == DEFAULT_WAITING_RUNS == 200
    assert limits.free_disk_bytes == DEFAULT_FREE_DISK_BYTES == 2 * GIGABYTE
    assert limits.store_bytes is None
    assert Simulator().limits == limits


def test_limits_are_read_from_a_file_and_an_option_takes_the_place_of_what_it_says(
    tmp_path: Path,
) -> None:
    written = tmp_path / "limits.json"
    written.write_text(json.dumps({"workers": 3, "waiting_runs": 5, "store_bytes": 1000}))

    assert limits_given(written) == Limits(workers=3, waiting_runs=5, store_bytes=1000)
    options = {"waiting_runs": "7", "free_disk_bytes": NO_LIMIT, "workers": None}
    assert limits_given(written, options) == Limits(
        workers=3, waiting_runs=7, free_disk_bytes=None, store_bytes=1000
    )
    assert limits_given(None, {"workers": "4"}) == Limits(workers=4)


@pytest.mark.parametrize(
    ("written", "says"),
    [
        ('{"workers": 0}', "greater than or equal to 1"),
        ('{"waiting": 3}', "waiting"),
        ("[1]", "a JSON object"),
        ("not json", "no limits read"),
    ],
)
def test_a_file_that_is_not_limits_is_refused_saying_why(
    tmp_path: Path, written: str, says: str
) -> None:
    path = tmp_path / "limits.json"
    path.write_text(written)

    with pytest.raises(InvalidRequest, match=says):
        limits_given(path)


def test_a_file_that_cannot_be_read_is_refused_saying_why(tmp_path: Path) -> None:
    with pytest.raises(InvalidRequest, match="no limits read"):
        limits_given(tmp_path / "none.json")


def test_the_servers_options_are_the_limits_with_a_file_beside_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    written = tmp_path / "limits.json"
    written.write_text(json.dumps({"workers": 3, "waiting_runs": 5}))
    parser = argparse.ArgumentParser()
    _add_limits(parser)

    args = parser.parse_args(["--limits", str(written), "--waiting-runs", "9"])
    assert _limits(args, parser) == Limits(workers=3, waiting_runs=9)

    args = parser.parse_args(["--free-disk-bytes", NO_LIMIT])
    assert _limits(args, parser) == Limits(free_disk_bytes=None)

    with pytest.raises(SystemExit):
        _limits(parser.parse_args(["--workers", "0"]), parser)
    assert "greater than or equal to 1" in capsys.readouterr().err


def test_a_server_makes_its_simulator_with_the_limits_it_is_given() -> None:
    server = create_server(0, limits=Limits(workers=3))
    try:
        assert server.simulator.limits == Limits(workers=3)
    finally:
        server.server_close()


def test_a_run_that_would_wait_past_the_limit_is_refused_in_words_with_nothing_written(
    tmp_path: Path, held_workers: None
) -> None:
    limits = Limits(workers=1, waiting_runs=1)
    with _simulator(tmp_path, limits) as simulator:
        running = scheduler.start(simulator, LONG, seed=1)
        waiting = scheduler.start(simulator, LONG, seed=2)
        written = _in_store(tmp_path)

        with pytest.raises(Conflict) as refused:
            scheduler.start(simulator, LONG, seed=3)

        _refused_in_words(refused.value, "1 run", "wait", "raise that limit")
        assert _in_store(tmp_path) == written
        assert [(s.run_id, s.epoch) for s in stored_runs(FolderStore(tmp_path))] == sorted(
            (s.run_id, s.epoch) for s in (running, waiting)
        )

        # A route says the same, as a conflict, and another may ask once one has left.
        answered = respond(simulator, "POST", f"/api/scenarios/{LONG}/runs?seed=3")
        assert answered.status == HTTPStatus.CONFLICT
        assert answered.body == {"error": refused.value.message}
        scheduler.cancel(simulator, waiting.run_id, waiting.epoch)
        assert scheduler.start(simulator, LONG, seed=4).seed == 4


def test_a_run_a_free_worker_takes_at_once_does_not_wait_and_is_not_refused(
    tmp_path: Path, held_workers: None
) -> None:
    with _simulator(tmp_path, Limits(workers=2, waiting_runs=0)) as simulator:
        scheduler.start(simulator, LONG, seed=1)
        scheduler.start(simulator, LONG, seed=2)

        with pytest.raises(Conflict) as refused:
            scheduler.start(simulator, LONG, seed=3)

        _refused_in_words(refused.value, "no run wait")


def test_a_fork_and_a_resume_are_refused_as_a_run_is_for_want_of_room(
    tmp_path: Path, held_workers: None
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as first:
        first.runs = objects
        ended = workers_support.with_one_day_committed(first, objects)

    with _simulator(tmp_path, Limits(workers=1, waiting_runs=0)) as simulator:
        scheduler.start(simulator, LONG, seed=1)
        written = _in_store(tmp_path)

        with pytest.raises(Conflict) as forked:
            scheduler.fork(simulator, ended.run_id, ended.epoch, 3600.0)
        with pytest.raises(Conflict) as resumed:
            scheduler.resume(simulator, ended.run_id, ended.epoch)

        _refused_in_words(forked.value, "no run wait")
        _refused_in_words(resumed.value, "no run wait")
        assert ended.manifest().status == Status.INTERRUPTED
        assert _in_store(tmp_path) == written


def test_a_run_on_a_disk_under_its_floor_is_refused_in_words_with_nothing_written(
    tmp_path: Path, held_workers: None
) -> None:
    objects = FolderStore(tmp_path)
    free = objects.free_bytes()
    assert free is not None
    floor = free + 10**15
    with _simulator(tmp_path, Limits(free_disk_bytes=floor)) as simulator:
        with pytest.raises(Conflict) as refused:
            scheduler.start(simulator, SHORT)

        _refused_in_words(refused.value, "free", in_words(floor), "lower that limit")
        assert _in_store(tmp_path) == []
        answered = respond(simulator, "POST", f"/api/scenarios/{SHORT}/runs")
        assert answered.status == HTTPStatus.CONFLICT


def test_a_run_is_not_refused_for_a_disk_with_no_floor_or_a_store_that_cannot_say(
    tmp_path: Path, held_workers: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(FolderStore, "free_bytes", lambda _: 1)
    with _simulator(tmp_path, Limits(free_disk_bytes=None)) as simulator:
        assert scheduler.start(simulator, LONG, seed=1).seed == 1

    # A store with no disk of its own has no figure to refuse by.
    monkeypatch.setattr(FolderStore, "free_bytes", lambda _: None)
    with _simulator(tmp_path, Limits(free_disk_bytes=10**18)) as simulator:
        assert scheduler.start(simulator, LONG, seed=2).seed == 2


def test_a_store_not_yet_made_says_what_is_free_on_the_disk_it_will_be_on(tmp_path: Path) -> None:
    assert FolderStore(tmp_path / "not" / "yet").free_bytes() == FolderStore(tmp_path).free_bytes()


def test_a_run_on_a_store_that_holds_its_limit_is_refused_in_words(
    tmp_path: Path, held_workers: None
) -> None:
    with _simulator(tmp_path, Limits(store_bytes=1)) as simulator:
        # An empty store holds nothing, and so has room for the first.
        running = scheduler.start(simulator, LONG, seed=1)
        written = _in_store(tmp_path)

        with pytest.raises(Conflict) as refused:
            scheduler.start(simulator, LONG, seed=2)

        _refused_in_words(refused.value, "the run store holds", "1 B", "delete some runs")
        assert _in_store(tmp_path) == written
        scheduler.cancel(simulator, running.run_id, running.epoch)


def test_what_a_store_holds_is_what_its_reports_say_and_what_no_epoch_holds(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        made.runs = objects
        reported = workers_support.with_one_day_committed(made, objects)
    usage = reported.usage()
    assert usage is not None and usage.commits == 1
    held = sum(path.stat().st_size for path in tmp_path.rglob("*") if path.is_file())
    report = (tmp_path / reported.run_id / str(reported.epoch) / "usage.json").stat().st_size

    # A report's own bytes are not counted, and all else is: the scenario's file too.
    assert held_bytes(objects) == held - report
    assert any(path.parts[-2] == "scenarios" for path in tmp_path.rglob("*.json"))


def test_a_queue_longer_than_a_lowered_limit_keeps_waiting_and_no_more_are_let_in(
    tmp_path: Path, held_workers: None
) -> None:
    with _simulator(tmp_path, Limits(workers=1)) as first:
        for seed in range(1, 5):
            scheduler.start(first, SHORT, seed=seed)
        assert len(scheduler.of(first).waiting()) == 3

    limits = Limits(workers=1, waiting_runs=1)
    with Simulator(runs=FolderStore(tmp_path), limits=limits) as second:
        made = scheduler.of(second)
        assert len(made.waiting()) == 2
        with pytest.raises(Conflict) as refused:
            made.start(SHORT, seed=5)
        _refused_in_words(refused.value, "2 runs", "1 run")


def test_a_worker_runs_at_a_lower_priority_than_who_started_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler, "work", workers_support.works_and_says_its_priority)
    said = tmp_path / workers_support.PRIORITY_SAID
    here = os.getpriority(os.PRIO_PROCESS, 0)
    with _simulator(tmp_path, Limits(workers=1)) as simulator:
        scheduler.start(simulator, SHORT)
        _until(said.exists, "the worker to say its priority")

    assert int(said.read_text()) == min(here + resources.WORKER_NICENESS, 20)
    assert os.getpriority(os.PRIO_PROCESS, 0) == here
