"""A stop that reaches a worker through the store (P17.9, decisions 0065 and
0067): the worker of a server that was killed is out of reach of any signal. It
reads the request between its moments and ends as a stop ends it, its commits and
their digests as they were; a request left behind stops nothing after it. A
playback of the server asked has no worker, and is stopped itself: the epoch ends
as a worker's does, whoever is watching it. Most of these work a playback's days
with no thread, so that nothing races what they say."""

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
from time import monotonic
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import interrupted, leases, playback
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand, PlaybackFailed
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    ObjectStore,
    Status,
    StoredRun,
    stored_run,
    stored_runs,
)
from greenhouse_sim.services.sensors import Stopped
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
# Time enough for a stop to find the claim written, and to see it expire.
LEASE_LEFT_S: Final = 2.0
START_HELD: Final = f"/api/scenarios/{BOX}/playback/start?hold=true"
DELIVERED: Final = "greenhouse_sim.services.playback.delivered_between"

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
    """An epoch told `status` by someone this test does not hold, with no claim."""
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


def _claimed(epoch: EpochStore, *, age_s: float = 0.0) -> None:
    """A claim written `age_s` ago, as a worker elsewhere holds it, and not written
    again."""
    assert epoch.objects.create(
        f"{epoch.run_id}/{epoch.epoch}/{leases.CLAIMS}/00000000.json",
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
    _claimed(epoch)

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
    # Told through a claim, and let go: a worker coming later finds it ended.
    assert leases.newest(_store(server), "run/0") == 1
    assert not epoch.worked()


def test_a_stop_of_an_epoch_whose_claim_expired_is_told_interrupted_through_the_next(
    server: Simulator,
) -> None:
    epoch = _epoch(_store(server), Status.RUNNING)
    _claimed(epoch, age_s=2 * leases.EXPIRES_AFTER_S)

    answer = respond(server, "POST", _stop_path(epoch))

    assert _run_of(answer.body).status == Status.INTERRUPTED
    assert not epoch.stop_asked()
    assert leases.newest(_store(server), "run/0") == 2


@pytest.mark.parametrize("status", [Status.QUEUED, Status.RUNNING])
def test_a_stop_of_an_epoch_with_a_claim_elsewhere_writes_the_request_whatever_its_status(
    server: Simulator, status: Status
) -> None:
    """A worker claims an epoch while it still waits, and may be seconds from running."""
    epoch = _epoch(_store(server), status)
    _claimed(epoch)

    answer = respond(server, "POST", _stop_path(epoch))

    assert _run_of(answer.body).status == status and _run_of(answer.body).stopping
    assert epoch.stop_asked()
    assert leases.newest(_store(server), "run/0") == 0


def test_a_worker_taking_an_epoch_up_as_a_stop_would_tell_it_is_asked_instead(
    tmp_path: Path,
) -> None:
    """The stop found no one, and is stopped just before its claim: the worker wins."""

    class TakenUpFirst(FolderStore):
        taken = False

        def create(self, name: str, data: bytes) -> bool:
            if not self.taken:
                self.taken = True
                assert worker.claim()
            return super().create(name, data)

    objects = TakenUpFirst(tmp_path / "runs")
    with _box(runs=objects) as server:
        epoch = _epoch(objects, Status.QUEUED)
        worker = EpochStore(FolderStore(objects.root), "run", 0)

        answer = respond(server, "POST", _stop_path(epoch))

        assert _run_of(answer.body).stopping
        assert epoch.manifest().status == Status.QUEUED
        assert epoch.stop_asked()
        assert worker.claimed()
        worker.let_go()


@pytest.mark.parametrize("starts", [execute, resume], ids=["execute", "resume"])
def test_a_worker_that_stops_as_it_was_asked_lets_its_claim_go(
    tmp_path: Path, starts: Callable[..., Status]
) -> None:
    with _box() as simulator:
        epoch = queued(simulator, FolderStore(tmp_path), BOX)
        epoch.ask_to_stop()

        assert starts(simulator, epoch, Free()) == Status.INTERRUPTED

    assert not epoch.worked()
    # Its claim and its letting go, and no time left in the store to wait out.
    assert leases.newest(epoch.objects, f"{epoch.run_id}/{epoch.epoch}") == 1
    assert EpochStore(epoch.objects, epoch.run_id, epoch.epoch).claim()


def test_a_worker_that_dies_before_it_looks_leaves_its_epoch_interrupted_as_its_claim_expires(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(interrupted, "RECHECK_EVERY_S", 0.05)
    epoch = _epoch(_store(server), Status.RUNNING)
    _claimed(epoch, age_s=leases.EXPIRES_AFTER_S - LEASE_LEFT_S)

    respond(server, "POST", _stop_path(epoch))

    _until(lambda: epoch.manifest().status == Status.INTERRUPTED, "the claim to expire")
    assert not stored_run(_store(server), "run", 0).stopping


def test_a_run_stopped_and_deleted_is_looked_at_no_more(
    server: Simulator, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(interrupted, "RECHECK_EVERY_S", 0.05)
    epoch = _epoch(_store(server), Status.RUNNING)
    _claimed(epoch)
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


def test_a_list_read_from_an_epochs_report_says_it_is_stopping(tmp_path: Path) -> None:
    """A list reads an epoch with a report without walking its folder."""
    objects = FolderStore(tmp_path / "runs")
    epoch = _epoch(objects, Status.RUNNING)
    epoch.write_usage([])
    assert stored_runs(objects)[0].stopping is False

    epoch.ask_to_stop()

    assert stored_runs(objects)[0].stopping is True
    assert stored_run(objects, epoch.run_id, epoch.epoch).stopping is True
    epoch.objects.put(
        f"{epoch.run_id}/{epoch.epoch}/manifest.json",
        epoch.manifest()
        .model_copy(update={"status": Status.INTERRUPTED})
        .model_dump_json()
        .encode(),
    )
    assert stored_runs(objects)[0].stopping is False


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


def _played(server: Simulator, *, clock: Callable[[], float] = monotonic) -> Playback:
    """The scenario's playback, kept as a start keeps it, its epoch running, with
    no thread: its days are the test's to work."""
    found = Playback(server, BOX, epochs=Epochs(objects=_store(server)), clock=clock)
    _epoch_of(server, found).set_status(Status.RUNNING)
    server.playbacks.made_once(BOX, lambda _: found)
    return found


def _epoch_of(server: Simulator, found: Playback) -> EpochStore:
    return EpochStore(_store(server), found.run_id, found.state().epoch)


def _delete_path(epoch: EpochStore) -> str:
    return f"/api/runs/{epoch.run_id}/epochs/{epoch.epoch}/delete"


def _broken(*_: object, **__: object) -> None:
    raise ArithmeticError("a numerical failure")


def _held_with_a_day_kept(server: Simulator) -> Playback:
    """Its clock held, past a day, with no page reading it."""
    found = _played(server)
    found.step_to(DAY_S)
    found.keep()
    return found


def _playing_with_a_day_kept(server: Simulator) -> Playback:
    """Its clock moving, on with no page reading it: all a playback does when
    the page that started it has gone."""
    now = [0.0]
    found = _played(server, clock=lambda: now[0])
    found.work_day(0)
    found.command(PlaybackCommand.PLAY)
    now[0] = DAY_S
    found.keep()
    return found


@pytest.mark.parametrize(
    ("playing", "made"),
    [(False, _held_with_a_day_kept), (True, _playing_with_a_day_kept)],
    ids=["paused", "its_page_gone"],
)
def test_a_stop_of_a_playback_ends_its_epoch_keeps_what_it_committed_and_lets_it_be_deleted(
    server: Simulator, playing: bool, made: Callable[[Simulator], Playback]
) -> None:
    found = made(server)
    epoch = _epoch_of(server, found)
    kept = _digests(epoch)
    assert len(kept) == 1
    assert found.epoch_held() == (None if playing else epoch.epoch)
    asked = respond(server, "GET", f"/api/runs/{epoch.run_id}/epochs/{epoch.epoch}")
    assert _run_of(asked.body).paused is not playing

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.OK
    run = _run_of(answer.body)
    assert run.status == Status.INTERRUPTED
    assert not run.stopping and not run.paused
    assert run.frontier_s == DAY_S
    assert not epoch.worked()
    assert _digests(epoch) == kept
    epoch.verify()
    # It is gone, and is not a scheduler's to look after.
    assert server.playbacks.get(BOX) is None
    assert server.scheduler is None
    assert respond(server, "POST", _delete_path(epoch)).status == HTTPStatus.OK
    assert stored_runs(_store(server)) == []


def test_a_stop_of_a_playback_changes_no_digest_and_the_epoch_carries_on_to_the_same_run(
    server: Simulator, tmp_path: Path
) -> None:
    whole = queued(server, FolderStore(tmp_path / "whole"), BOX)
    assert execute(server, whole, Free()) == Status.FINISHED
    epoch = _epoch_of(server, _held_with_a_day_kept(server))

    assert respond(server, "POST", _stop_path(epoch)).status == HTTPStatus.OK

    assert _digests(epoch) == _digests(whole)[:1]
    assert resume(server, epoch, Free()) == Status.FINISHED
    assert _digests(epoch) == _digests(whole)
    epoch.verify()


def test_a_stop_of_a_playback_failed_with_no_one_told_says_why_and_lets_it_be_deleted(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = _played(server)
    epoch = _epoch_of(server, found)
    with monkeypatch.context() as patch:
        patch.setattr(DELIVERED, _broken)
        assert not found.work_day(0)
    assert epoch.manifest().status == Status.RUNNING

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.OK
    run = _run_of(answer.body)
    assert run.status == Status.FAILED
    assert run.reason == "its run could not be worked out (ArithmeticError)"
    assert respond(server, "POST", _delete_path(epoch)).status == HTTPStatus.OK


def test_a_playback_failed_and_said_so_is_not_stopped_is_deleted_and_still_says_why(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = _played(server)
    epoch = _epoch_of(server, found)
    with monkeypatch.context() as patch:
        patch.setattr(DELIVERED, _broken)
        assert not found.work_day(0)
    found.keep()

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.CONFLICT
    assert "is failed: it is not being computed" in str(answer.body)
    assert respond(server, "POST", _delete_path(epoch)).status == HTTPStatus.OK
    assert server.playbacks.get(BOX) is found
    with pytest.raises(PlaybackFailed):
        found.state()


def test_an_epoch_the_store_could_not_be_told_had_failed_is_told_by_a_stop(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = _played(server)
    epoch = _epoch_of(server, found)
    with monkeypatch.context() as patch:
        patch.setattr(DELIVERED, _broken)
        assert not found.work_day(0)

    def unwritable(*_: object, **__: object) -> None:
        raise OSError("the store cannot be written")

    with monkeypatch.context() as patch:
        patch.setattr(EpochStore, "set_status", unwritable)
        with pytest.raises(OSError, match="cannot be written"):
            found.keep()
    assert epoch.manifest().status == Status.RUNNING

    answer = respond(server, "POST", _stop_path(epoch))

    assert answer.status == HTTPStatus.OK
    assert _run_of(answer.body).status == Status.FAILED


def test_a_playback_whose_thread_cannot_be_started_leaves_an_epoch_that_can_be_deleted(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts = threading.Thread.start

    def refused(thread: threading.Thread) -> None:
        if thread.name.startswith("playback of"):
            raise RuntimeError("can't start new thread")
        starts(thread)

    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", refused)
        with pytest.raises(RuntimeError, match="new thread"):
            playback.start(server, BOX, hold=True)

    assert server.playbacks.get(BOX) is None
    run = stored_runs(_store(server))[0]
    assert run.status == Status.FAILED
    assert not EpochStore(_store(server), run.run_id, run.epoch).worked()
    path = f"/api/runs/{run.run_id}/epochs/{run.epoch}/delete"
    assert respond(server, "POST", path).status == HTTPStatus.OK


def test_a_playback_stopped_opens_no_epoch_no_one_could_end(server: Simulator) -> None:
    found = _played(server)
    epoch = _epoch_of(server, found)
    assert respond(server, "POST", _stop_path(epoch)).status == HTTPStatus.OK

    # A restart under way as the stop was answered, its playback in hand.
    with pytest.raises(Conflict, match="no longer works"):
        found.command(PlaybackCommand.RESTART)

    assert [run.epoch for run in stored_runs(_store(server))] == [epoch.epoch]


def test_a_start_after_a_stop_of_its_playback_plays_the_run_as_its_next_epoch(
    server: Simulator,
) -> None:
    started = respond(server, "POST", START_HELD)
    assert started.status == HTTPStatus.OK and isinstance(started.body, dict)
    run_id, number = started.body["run_id"], started.body["epoch"]
    assert isinstance(run_id, str) and isinstance(number, int)
    epoch = EpochStore(_store(server), run_id, number)

    # The answer waits for its thread, as long as a stop waits: past that it reads
    # stopping, which is no end, and it is looked at until it has one.
    assert respond(server, "POST", _stop_path(epoch)).status == HTTPStatus.OK
    _until(lambda: epoch.manifest().status == Status.INTERRUPTED, "its thread to say so")
    assert not epoch.worked()

    again = respond(server, "POST", START_HELD)
    assert again.status == HTTPStatus.OK and isinstance(again.body, dict)
    assert (again.body["run_id"], again.body["epoch"]) == (run_id, number + 1)
    _until(
        lambda: respond(server, "POST", _delete_path(epoch)).status == HTTPStatus.OK,
        "the stopped epoch to be deleted",
    )


def test_a_stop_its_thread_is_slow_to_heed_reads_stopping_and_nothing_deletes_under_it(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    working, go_on = threading.Event(), threading.Event()

    def parked(*_: object, **__: object) -> None:
        working.set()
        go_on.wait(WAIT_S)
        raise Stopped

    monkeypatch.setattr(DELIVERED, parked)
    monkeypatch.setattr("greenhouse_sim.services.playback.STOP_WAIT_S", 0.0)
    playback.start(server, BOX, hold=True)
    found = playback.playback(server, BOX)
    assert working.wait(WAIT_S)
    epoch = _epoch_of(server, found)
    try:
        answer = respond(server, "POST", _stop_path(epoch))
        assert answer.status == HTTPStatus.OK
        assert _run_of(answer.body).status == Status.RUNNING
        assert _run_of(answer.body).stopping
        assert server.playbacks.get(BOX) is None
        assert respond(server, "POST", _delete_path(epoch)).status == HTTPStatus.CONFLICT

        # Asked again, it is still that playback's to end, not a worker's.
        again = respond(server, "POST", _stop_path(epoch))
        assert again.status == HTTPStatus.OK
        assert _run_of(again.body).stopping
        assert server.scheduler is None
    finally:
        go_on.set()
    found.finish(monotonic() + WAIT_S)

    assert epoch.manifest().status == Status.INTERRUPTED
    assert not stored_run(_store(server), epoch.run_id, epoch.epoch).stopping
    assert respond(server, "POST", _delete_path(epoch)).status == HTTPStatus.OK


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
    _claimed(epoch)

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
