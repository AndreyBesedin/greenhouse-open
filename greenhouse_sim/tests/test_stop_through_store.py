"""A stop that reaches a worker through the store (P17.9, decisions 0065 and
0067): the worker of a server that was killed is out of reach of any signal. It
reads the request between its moments and ends as a stop ends it, its commits and
their digests as they were; a request left behind stops nothing after it."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import interrupted, leases
from greenhouse_sim.services.playback import Playback, PlaybackFailed
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    ObjectStore,
    Status,
    StoredRun,
    stored_run,
)
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Stepped, execute, queued, resume

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

BOX: Final = "stop_box"
ONE_SENSOR: Final = ("temperature_front",)
# Long enough to stop with a day committed and a day yet to come.
DAYS: Final = 2
# Too long for a free worker to end before it is stopped, whatever the machine.
LONG_DAYS: Final = 2_000
SECONDS_PER_DAY: Final = 2
PACED_SEED: Final = 1
FREE_SEED: Final = 2
WAIT_S: Final = 120.0
LONG_AGO: Final = timedelta(seconds=leases.EXPIRES_AFTER_S * 10)
# Time enough for a stop to find the lease written, and to see it expire.
LEASE_LEFT_S: Final = 2.0

# A server that starts a run of each kind, says what it started and stays, until
# it is killed: its workers are processes of their own.
SERVER: Final = f"""
import json, sys, time
from pathlib import Path
from greenhouse_sim.api.routes import respond
from greenhouse_sim.services.run_store import FolderStore
from short_runs import cut, simulator_of

made = simulator_of(
    cut("climate_box", days={LONG_DAYS}, sensors={ONE_SENSOR!r}, greenhouse_id="{BOX}"),
    runs=FolderStore(Path(sys.argv[1])),
)
paced = respond(
    made, "POST", "/api/scenarios/{BOX}/runs?seed={PACED_SEED}&seconds_per_day={SECONDS_PER_DAY}"
)
free = respond(made, "POST", "/api/scenarios/{BOX}/runs?seed={FREE_SEED}")
print(json.dumps(dict(
    paced=paced.body, free=free.body, pids=[w.pid for w in made.scheduler.workers()]
), default=str), flush=True)
time.sleep(3600)
"""


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


def _box(days: int = DAYS, **given: Any) -> Simulator:
    return simulator_of(
        cut("climate_box", days=days, sensors=ONE_SENSOR, greenhouse_id=BOX), **given
    )


def _digests(epoch: EpochStore) -> list[str]:
    return [commit.digest for commit in epoch.commits()]


def _lives(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _stop_path(run: StoredRun | EpochStore) -> str:
    number = run.epoch
    return f"/api/runs/{run.run_id}/epochs/{number}/stop"


def _run_of(body: object) -> StoredRun:
    return StoredRun.model_validate(body)


def test_a_stop_asked_keeps_what_was_committed_and_its_digests_and_stops_nothing_resumed(
    tmp_path: Path,
) -> None:
    with _box() as simulator:
        whole = queued(simulator, FolderStore(tmp_path / "whole"), BOX)
        assert execute(simulator, whole, Free()) == Status.FINISHED
        epoch = queued(simulator, FolderStore(tmp_path / "runs"), BOX)

        def barriers() -> Iterator[float]:
            yield DAY_S
            epoch.ask_to_stop()
            yield DAYS * DAY_S

        assert execute(simulator, epoch, Stepped(barriers())) == Status.INTERRUPTED
        assert epoch.manifest().status == Status.INTERRUPTED
        assert not epoch.worked()
        assert epoch.frontier_s() == DAY_S
        assert _digests(epoch) == _digests(whole)[:1]
        # The request lies beside what the commits name, and is none of it.
        assert epoch.stop_asked()
        epoch.verify()

        assert resume(simulator, epoch, Free()) == Status.FINISHED
    assert not epoch.stop_asked()
    assert _digests(epoch) == _digests(whole)
    epoch.verify()


def test_a_stop_asked_of_an_epoch_waiting_ends_its_worker_at_its_first_look(
    tmp_path: Path,
) -> None:
    with _box() as simulator:
        epoch = queued(simulator, FolderStore(tmp_path), BOX)
        epoch.ask_to_stop()

        # As a worker takes an epoch up, whether it has begun or not.
        assert resume(simulator, epoch, Free()) == Status.INTERRUPTED
    assert epoch.commits() == []
    assert epoch.stop_asked()


@pytest.mark.parametrize("asked_again", ["queue_again", "set_status"])
def test_a_stop_left_behind_is_forgotten_when_the_epoch_waits_again(
    tmp_path: Path, asked_again: str
) -> None:
    epoch = _epoch(FolderStore(tmp_path), Status.INTERRUPTED)
    epoch.ask_to_stop()

    if asked_again == "queue_again":
        epoch.queue_again(scenario_file=None, seconds_per_day=None)
    else:
        epoch.set_status(Status.QUEUED)

    assert epoch.manifest().status == Status.QUEUED
    assert not epoch.stop_asked()


def _epoch(objects: ObjectStore, status: Status, *, age: timedelta = LONG_AGO) -> EpochStore:
    """An epoch told `status` by someone this test does not hold, with no lease."""
    return EpochStore.create(
        objects,
        EpochManifest(
            run_id="run",
            epoch=0,
            scenario_id=BOX,
            layout="default",
            status=status,
            created_at=datetime.now(UTC) - age,
        ),
    )


def _leased(epoch: EpochStore, *, age_s: float = 0.0) -> None:
    """A lease written `age_s` ago, as a worker elsewhere writes it, and not written
    again."""
    epoch.objects.put(
        f"{epoch.run_id}/{epoch.epoch}/{leases.LEASE}",
        json.dumps({"refreshed_at": time.time() - age_s}).encode(),
    )


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Simulator]:
    """A server over a store, whose workers are none of what the tests ask about."""
    with _box(runs=FolderStore(tmp_path / "runs")) as made:
        yield made


def _store(server: Simulator) -> ObjectStore:
    assert server.runs is not None
    return server.runs


def test_a_worker_elsewhere_is_asked_to_stop_and_the_answers_say_it_is_stopping(
    server: Simulator,
) -> None:
    epoch = _epoch(_store(server), Status.RUNNING)
    _leased(epoch)

    # Twice: the second finds it asked and is told the same.
    for _ in range(2):
        answer = respond(server, "POST", _stop_path(epoch))
        assert answer.status == HTTPStatus.OK
        assert _run_of(answer.body).status == Status.RUNNING
        assert _run_of(answer.body).stopping
    assert epoch.stop_asked()
    assert stored_run(_store(server), "run", 0).stopping

    # Nothing else takes the epoch from a worker that has not looked yet.
    resumed = respond(server, "POST", "/api/runs/run/epochs/0/resume")
    assert resumed.status == HTTPStatus.CONFLICT
    deleted = respond(server, "POST", "/api/runs/run/epochs/0/delete")
    assert deleted.status == HTTPStatus.CONFLICT
    assert epoch.stop_asked()

    epoch.set_status(Status.INTERRUPTED)
    assert not stored_run(_store(server), "run", 0).stopping
    refused = respond(server, "POST", _stop_path(epoch))
    assert refused.status == HTTPStatus.CONFLICT
    assert respond(server, "POST", "/api/runs/run/epochs/0/delete").status == HTTPStatus.OK


def test_a_stop_of_an_epoch_no_one_works_is_told_interrupted_at_once(server: Simulator) -> None:
    epoch = _epoch(_store(server), Status.RUNNING)

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.OK
    shown = _run_of(answer.body)
    assert shown.status == Status.INTERRUPTED and not shown.stopping
    assert not epoch.stop_asked()


def test_a_worker_that_dies_before_it_looks_leaves_its_epoch_interrupted_as_its_lease_expires(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(interrupted, "RECHECK_EVERY_S", 0.05)
    epoch = _epoch(_store(server), Status.RUNNING)
    _leased(epoch, age_s=leases.EXPIRES_AFTER_S - LEASE_LEFT_S)

    respond(server, "POST", _stop_path(epoch))

    _until(lambda: epoch.manifest().status == Status.INTERRUPTED, "the lease to expire")
    assert not stored_run(_store(server), "run", 0).stopping


def test_a_run_stopped_and_deleted_is_looked_at_no_more(
    server: Simulator, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(interrupted, "RECHECK_EVERY_S", 0.05)
    epoch = _epoch(_store(server), Status.RUNNING)
    _leased(epoch)
    respond(server, "POST", _stop_path(epoch))

    epoch.set_status(Status.INTERRUPTED)
    assert respond(server, "POST", "/api/runs/run/epochs/0/delete").status == HTTPStatus.OK

    _until(
        lambda: not any(thread.name == "epoch asked to stop" for thread in threading.enumerate()),
        "the look at it to end",
    )
    assert "could not be looked at" not in caplog.text


def test_a_stop_of_an_epoch_just_queued_elsewhere_is_kept_for_the_worker_that_takes_it(
    server: Simulator,
) -> None:
    epoch = _epoch(_store(server), Status.QUEUED, age=timedelta(0))

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.OK
    shown = _run_of(answer.body)
    assert shown.status == Status.QUEUED and shown.stopping
    assert epoch.stop_asked()


@pytest.mark.parametrize("status", [Status.FINISHED, Status.FAILED, Status.INTERRUPTED])
def test_a_stop_of_an_epoch_that_has_ended_is_refused_and_asks_nothing(
    server: Simulator, status: Status
) -> None:
    epoch = _epoch(_store(server), status)

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.CONFLICT
    assert f"is {status}: it is not being computed" in str(answer.body)
    assert not epoch.stop_asked()
    assert epoch.manifest().status == status


def test_a_stop_asked_as_a_worker_ended_does_not_call_it_stopping(server: Simulator) -> None:
    epoch = _epoch(_store(server), Status.FINISHED)

    epoch.ask_to_stop()

    assert not stored_run(_store(server), "run", 0).stopping


def test_a_stop_of_an_epoch_the_store_does_not_hold_is_not_found(server: Simulator) -> None:
    answer = respond(server, "POST", "/api/runs/run/epochs/7/stop")

    assert answer.status == HTTPStatus.NOT_FOUND


def test_a_stop_of_an_epoch_played_in_the_viewer_says_so_and_asks_nothing(
    server: Simulator,
) -> None:
    # The fixture's closing the simulator stops the playback.
    started = respond(server, "POST", f"/api/scenarios/{BOX}/playback/start?hold=true")
    assert started.status == HTTPStatus.OK and isinstance(started.body, dict)
    run_id, number = started.body["run_id"], started.body["epoch"]
    assert isinstance(run_id, str) and isinstance(number, int)
    epoch = EpochStore(_store(server), run_id, number)

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.CONFLICT
    assert "stops with its playback" in str(answer.body)
    assert not epoch.stop_asked()


def test_a_failed_playback_of_another_run_does_not_keep_a_worker_elsewhere_from_stopping(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> None:
        raise ArithmeticError("a numerical failure")

    # Its day worked here and not by its thread, which is never started: it has
    # failed by the time it is kept, as one that failed while it played is.
    monkeypatch.setattr("greenhouse_sim.services.playback.delivered_between", broken)
    failed = Playback(server, BOX)
    assert not failed.work_day(0)
    server.playbacks.made_once(BOX, lambda _: failed)
    with pytest.raises(PlaybackFailed):
        failed.state()
    epoch = _epoch(_store(server), Status.RUNNING)
    _leased(epoch)

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.OK
    assert _run_of(answer.body).stopping
    assert epoch.stop_asked()


def test_workers_a_killed_server_left_stop_through_the_store_and_the_run_is_deleted_or_resumed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    objects = FolderStore(root)
    process = subprocess.Popen(
        [sys.executable, "-c", SERVER, str(root)],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        text=True,
    )
    pids: list[int] = []
    try:
        assert process.stdout is not None
        said = json.loads(process.stdout.readline())
        pids = said["pids"]
        paced = EpochStore(objects, said["paced"]["run_id"], said["paced"]["epoch"])
        free = EpochStore(objects, said["free"]["run_id"], said["free"]["epoch"])
        _until(
            lambda: paced.frontier_s() >= DAY_S and free.frontier_s() >= DAY_S,
            "a day of each to be committed",
        )
        process.kill()
        process.wait()
        assert all(_lives(pid) for pid in pids)

        with _box(LONG_DAYS, runs=FolderStore(root)) as second:
            for epoch in (paced, free):
                assert epoch.manifest().status == Status.RUNNING
                answer = respond(second, "POST", _stop_path(epoch))
                assert answer.status == HTTPStatus.OK
                assert _run_of(answer.body).stopping
            refused = respond(second, "POST", f"/api/runs/{free.run_id}/epochs/{free.epoch}/delete")
            assert refused.status == HTTPStatus.CONFLICT

        # The server that asked is gone too: what asks is in the store.
        _until(lambda: not any(_lives(pid) for pid in pids), "the workers to exit")
        for epoch in (paced, free):
            assert epoch.manifest().status == Status.INTERRUPTED
            assert not epoch.worked()
            assert epoch.frontier_s() >= DAY_S
            epoch.verify()
        kept = _digests(paced)

        with _box(LONG_DAYS, runs=FolderStore(root)) as third:
            deleted = respond(third, "POST", f"/api/runs/{free.run_id}/epochs/{free.epoch}/delete")
            assert deleted.status == HTTPStatus.OK
            path = f"/api/runs/{paced.run_id}/epochs/{paced.epoch}/resume"
            assert respond(third, "POST", path).status == HTTPStatus.OK
            # The request left behind stops nothing: the work goes on past it.
            _until(lambda: len(paced.commits()) > len(kept), "the run to be carried on")
            assert paced.manifest().status == Status.RUNNING
            assert not paced.stop_asked()
        assert _digests(paced)[: len(kept)] == kept

        with _box(LONG_DAYS) as reference:
            whole = queued(reference, FolderStore(tmp_path / "whole"), BOX, seed=PACED_SEED)
            days = len(paced.commits())
            moments = [(day + 1) * DAY_S for day in range(days)]
            assert execute(reference, whole, Stepped(moments)) == Status.INTERRUPTED
        assert _digests(paced) == _digests(whole)
    finally:
        process.kill()
        process.wait()
        for pid in pids:
            if _lives(pid):
                os.kill(pid, signal.SIGKILL)
