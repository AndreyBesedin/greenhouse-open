"""Who works an epoch (P17.9, decision 0065): a process that says an epoch runs
holds a lease on it, written again while it runs and gone when it ended, so
that an epoch `running` that no one writes can be told from one that is.

Its thread is ordered exactly against what its epoch is told: a thread's sleep
waits for the test to wake it (`_Beats`), and what comes between its reading the
store and its writing is done from within the write."""

import json
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Final

import pytest

from greenhouse_sim.services import leases, scheduler, workers
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    ObjectStore,
    Status,
)
from greenhouse_sim.services.simulator import Simulator

WAIT_S: Final = 30.0


@pytest.fixture
def epoch(tmp_path: Path) -> EpochStore:
    return EpochStore.create(
        FolderStore(tmp_path),
        EpochManifest(
            run_id="run", epoch=0, scenario_id="s", layout="default", created_at=datetime.now(UTC)
        ),
    )


def _lease(epoch: EpochStore) -> str:
    return f"{epoch.run_id}/{epoch.epoch}/{leases.LEASE}"


def _refreshed_at(epoch: EpochStore) -> float:
    data = epoch.objects.get(_lease(epoch))
    assert data is not None
    return float(json.loads(data)["refreshed_at"])


class _Beats:
    """Keeps every lease's thread in its sleep until a test wakes it."""

    def __init__(self) -> None:
        self._asleep: dict[threading.Thread, threading.Event] = {}
        self._seen: set[threading.Thread] = set()

    def sleep(self, _seconds: float) -> None:
        woken = threading.Event()
        self._asleep[threading.current_thread()] = woken
        woken.wait()

    def newest(self) -> threading.Thread:
        """The thread that has gone to sleep since this was last asked."""
        deadline = time.monotonic() + WAIT_S
        while True:
            for thread in list(self._asleep):
                if thread not in self._seen:
                    self._seen.add(thread)
                    return thread
            assert time.monotonic() < deadline, "waited for a lease's thread"
            time.sleep(0.001)

    def wake(self, thread: threading.Thread) -> bool:
        """Lets the thread beat once, and says whether it goes on beating."""
        self._asleep.pop(thread).set()
        deadline = time.monotonic() + WAIT_S
        while thread.is_alive() and thread not in self._asleep:
            assert time.monotonic() < deadline, "waited for a lease's thread to beat"
            time.sleep(0.001)
        return thread.is_alive()

    def wake_all(self) -> None:
        for thread in list(self._asleep):
            self._asleep.pop(thread).set()
            thread.join(1.0)


@pytest.fixture
def beats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Beats]:
    held = _Beats()
    monkeypatch.setattr(leases, "time", SimpleNamespace(time=time.time, sleep=held.sleep))
    yield held
    # A thread ends when it finds its lease gone.
    for lease in tmp_path.rglob(leases.LEASE):
        lease.unlink()
    held.wake_all()


def _ended_and_queued(epoch: EpochStore) -> None:
    """As a resume leaves an epoch that was running."""
    epoch.set_status(Status.INTERRUPTED)
    epoch.queue_again(scenario_file=None, seconds_per_day=None)


def test_an_epoch_told_to_run_is_held_until_it_is_told_it_ended(epoch: EpochStore) -> None:
    assert not epoch.worked()

    epoch.set_status(Status.RUNNING)
    assert epoch.worked()

    epoch.set_status(Status.INTERRUPTED)
    assert not epoch.worked()
    assert epoch.objects.get(_lease(epoch)) is None


def test_a_lease_not_written_for_a_while_is_not_believed(epoch: EpochStore) -> None:
    epoch.set_status(Status.RUNNING)
    written = _refreshed_at(epoch)

    assert epoch.worked(now=written + leases.EXPIRES_AFTER_S)
    assert not epoch.worked(now=written + leases.EXPIRES_AFTER_S + 1)
    epoch.set_status(Status.FINISHED)


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        time.sleep(0.01)


def test_the_lease_of_a_worked_epoch_is_written_again_while_it_is_worked(
    epoch: EpochStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leases, "REFRESH_EVERY_S", 0.02)
    epoch.set_status(Status.RUNNING)
    before = _refreshed_at(epoch)

    _until(lambda: _refreshed_at(epoch) > before, "the lease to be written again")
    epoch.set_status(Status.FINISHED)


def test_an_epoch_told_it_ended_by_another_process_is_not_given_a_lease_again(
    epoch: EpochStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leases, "REFRESH_EVERY_S", 0.02)
    epoch.set_status(Status.RUNNING)
    # Said to have ended by the scheduler, as for a worker that died, which is
    # another process: this one's heartbeat must not write the lease back.
    ended = epoch.manifest().model_copy(update={"status": Status.INTERRUPTED})
    epoch.objects.put(
        f"{epoch.run_id}/{epoch.epoch}/manifest.json", ended.model_dump_json().encode()
    )
    epoch.objects.delete(_lease(epoch))

    time.sleep(0.2)

    assert not epoch.worked()
    assert epoch.objects.get(_lease(epoch)) is None


def test_a_lease_that_is_not_one_is_not_believed(epoch: EpochStore) -> None:
    epoch.objects.put(_lease(epoch), b"not json")

    assert not epoch.worked()


def test_a_thread_that_wakes_on_an_epoch_queued_again_leaves_it_free_for_a_worker(
    epoch: EpochStore, beats: _Beats
) -> None:
    epoch.set_status(Status.RUNNING)
    old = beats.newest()
    _ended_and_queued(epoch)

    assert not beats.wake(old)

    assert epoch.objects.get(_lease(epoch)) is None
    assert workers.check_resumable(epoch) == 0.0


def test_a_thread_that_wakes_on_a_new_holders_lease_leaves_it_as_it_is(
    epoch: EpochStore, beats: _Beats
) -> None:
    epoch.set_status(Status.RUNNING)
    old = beats.newest()
    _ended_and_queued(epoch)
    epoch.set_status(Status.RUNNING)
    new = beats.newest()
    theirs = epoch.objects.get(_lease(epoch))

    assert not beats.wake(old)
    assert epoch.objects.get(_lease(epoch)) == theirs

    # And the new holder is not put off by it.
    assert beats.wake(new)
    written = epoch.objects.get(_lease(epoch))
    assert written is not None and theirs is not None
    assert json.loads(written)["holder"] == json.loads(theirs)["holder"]
    assert _refreshed_at(epoch) >= json.loads(theirs)["refreshed_at"]


def _told_as_it_writes(
    monkeypatch: pytest.MonkeyPatch, before: Callable[[], None], after: Callable[[], None]
) -> None:
    """What happens around a thread's next write, once it has read the store."""
    real = leases._write

    def writes(objects: ObjectStore, home: str, holder: str) -> None:
        before()
        real(objects, home, holder)
        after()

    monkeypatch.setattr(leases, "_write", writes)


def _nothing() -> None:
    pass


@pytest.mark.parametrize(
    "told",
    [lambda epoch: epoch.set_status(Status.INTERRUPTED), _ended_and_queued],
    ids=["ended", "ended and queued again"],
)
def test_an_epoch_that_ends_just_before_its_lease_is_written_is_left_with_none(
    epoch: EpochStore,
    beats: _Beats,
    monkeypatch: pytest.MonkeyPatch,
    told: Callable[[EpochStore], None],
) -> None:
    epoch.set_status(Status.RUNNING)
    thread = beats.newest()
    _told_as_it_writes(monkeypatch, lambda: told(epoch), _nothing)

    assert not beats.wake(thread)

    assert not epoch.worked()
    assert epoch.objects.get(_lease(epoch)) is None


def test_an_epoch_that_ends_just_after_its_lease_is_written_is_left_with_none(
    epoch: EpochStore, beats: _Beats, monkeypatch: pytest.MonkeyPatch
) -> None:
    epoch.set_status(Status.RUNNING)
    thread = beats.newest()
    _told_as_it_writes(monkeypatch, _nothing, lambda: epoch.set_status(Status.INTERRUPTED))

    assert not beats.wake(thread)

    assert epoch.objects.get(_lease(epoch)) is None


def test_a_thread_finding_its_epoch_ended_does_not_clear_a_lease_another_has_taken(
    epoch: EpochStore, beats: _Beats, monkeypatch: pytest.MonkeyPatch
) -> None:
    epoch.set_status(Status.RUNNING)
    thread = beats.newest()
    theirs = json.dumps({"refreshed_at": time.time(), "holder": "another"}).encode()
    _told_as_it_writes(
        monkeypatch,
        lambda: epoch.set_status(Status.INTERRUPTED),
        lambda: epoch.objects.put(_lease(epoch), theirs),
    )

    assert not beats.wake(thread)

    assert epoch.objects.get(_lease(epoch)) == theirs


def test_a_lease_of_the_format_before_holders_is_believed_and_no_thread_writes_it(
    epoch: EpochStore, beats: _Beats
) -> None:
    epoch.set_status(Status.RUNNING)
    thread = beats.newest()
    written = time.time()
    old_format = json.dumps({"refreshed_at": written}).encode()
    epoch.objects.put(_lease(epoch), old_format)

    assert epoch.worked(now=written + leases.EXPIRES_AFTER_S)
    assert not epoch.worked(now=written + leases.EXPIRES_AFTER_S + 1)
    assert not beats.wake(thread)
    assert epoch.objects.get(_lease(epoch)) == old_format

    # An epoch that is carried on from it is refused while it is believed.
    epoch.set_status(Status.INTERRUPTED)
    epoch.objects.put(_lease(epoch), old_format)
    with pytest.raises(Conflict, match="worked by a process still"):
        workers.check_resumable(epoch)

    # And whoever takes the epoch up writes over it.
    epoch.set_status(Status.RUNNING)
    taken = epoch.objects.get(_lease(epoch))
    assert taken is not None and "holder" in json.loads(taken)


def test_an_epoch_carried_on_is_taken_by_its_worker_whenever_an_old_thread_wakes(
    tmp_path: Path, beats: _Beats, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An epoch ended in a process that goes on, as a live playback's is, and asked
    of the scheduler to be carried on; then a worker's whole way in, but for the
    process it runs in and the days it works out."""
    objects = FolderStore(tmp_path / "runs")
    epoch = EpochStore.create(
        objects,
        EpochManifest(
            run_id="run",
            epoch=0,
            scenario_id="climate_box",
            layout="default",
            created_at=datetime.now(UTC),
        ),
    )
    epoch.set_status(Status.RUNNING)
    old = beats.newest()
    epoch.set_status(Status.INTERRUPTED)
    # The worker asked for has not begun when the old thread wakes.
    monkeypatch.setattr(scheduler.Scheduler, "_launch", lambda _self: None)

    def days_worked_out(_simulator: Simulator, worked: EpochStore, *_rest: object) -> Status:
        worked.set_status(Status.RUNNING)
        assert worked.worked()
        worked.set_status(Status.FINISHED)
        return Status.FINISHED

    monkeypatch.setattr(workers, "_drive", days_worked_out)

    with Simulator(runs=objects) as simulator:
        scheduling = scheduler.Scheduler(simulator, objects.root, limit=1)
        try:
            scheduling.resume("run", 0)
            assert epoch.manifest().status == Status.QUEUED

            goes_on = beats.wake(old)

            with pytest.raises(SystemExit) as ended:
                scheduler.work(str(objects.root), "run", 0)
            assert ended.value.code == 0
            assert not goes_on
            assert epoch.manifest().status == Status.FINISHED
            assert epoch.objects.get(_lease(epoch)) is None
        finally:
            scheduling.close()
