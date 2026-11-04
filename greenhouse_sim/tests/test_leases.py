"""Who works an epoch (P17.9, P18.4, decisions 0065 and 0067): a process that says
an epoch runs holds a claim on it, written again while it runs and let go when it
ended, so that an epoch `running` that no one writes can be told from one that is.

Its thread is ordered exactly against what its epoch is told: a thread's sleep
waits for the test to wake it (`_Beats`), and what comes between its reading the
store and its writing is done from within the write (`_Stopped`)."""

import json
import shutil
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final

import pytest

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import leases, scheduler, workers
from greenhouse_sim.services.checkpoints import upload_checkpoint
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    Status,
)
from greenhouse_sim.services.simulator import Simulator

# A worker starts from nothing and imports what it is told to run by name.
sys.path.insert(0, str(Path(__file__).parent))

import workers_support

WAIT_S: Final = 30.0


def _manifest() -> EpochManifest:
    return EpochManifest(
        run_id="run", epoch=0, scenario_id="s", layout="default", created_at=datetime.now(UTC)
    )


@pytest.fixture
def epoch(tmp_path: Path) -> EpochStore:
    return EpochStore.create(FolderStore(tmp_path), _manifest())


def _claim(epoch: EpochStore) -> str:
    """The name of the epoch's newest claim."""
    return epoch.objects.names(f"{epoch.run_id}/{epoch.epoch}/{leases.CLAIMS}/")[-1]


def _old_lease(epoch: EpochStore) -> str:
    return f"{epoch.run_id}/{epoch.epoch}/{leases.LEASE}"


def _refreshed_at(epoch: EpochStore) -> float:
    data = epoch.objects.get(_claim(epoch))
    assert data is not None
    return float(json.loads(data)["refreshed_at"])


class _Beats:
    """Keeps every lease's thread in its sleep until a test wakes it."""

    def __init__(self) -> None:
        self._asleep: dict[threading.Thread, threading.Event] = {}
        self._seen: set[threading.Thread] = set()
        # A thread an earlier test of this process left to end at its next beat is
        # none of this test's: it sleeps as it would, and is not taken for a new one.
        self._before = set(threading.enumerate())

    def sleep(self, seconds: float) -> None:
        if threading.current_thread() in self._before:
            threading.Event().wait(seconds)
            return
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
    # A thread ends when it finds its claim gone.
    for claims in tmp_path.rglob(leases.CLAIMS):
        shutil.rmtree(claims)
    held.wake_all()


def _ended_and_queued(epoch: EpochStore) -> None:
    """As a resume leaves an epoch that was running."""
    epoch.set_status(Status.INTERRUPTED)
    epoch.queue_again(scenario_file=None, seconds_per_day=None)


class _Stopped(FolderStore):
    """A store whose claim's thread does `before` and `after`, once each, around its
    next write or creation: it has read the store and is stopped there."""

    before: Callable[[], None] | None = None
    after: Callable[[], None] | None = None

    def _beating(self) -> bool:
        return threading.current_thread().name.startswith("lease of")

    def _around(self, write: Callable[[], bool | None]) -> bool | None:
        if self._beating() and self.before is not None:
            before, self.before = self.before, None
            before()
        written = write()
        if self._beating() and self.after is not None:
            after, self.after = self.after, None
            after()
        return written

    def put(self, name: str, data: bytes) -> None:
        self._around(lambda: super(_Stopped, self).put(name, data))

    def create(self, name: str, data: bytes) -> bool:
        return bool(self._around(lambda: super(_Stopped, self).create(name, data)))


def test_an_epoch_told_to_run_is_held_until_it_is_told_it_ended(epoch: EpochStore) -> None:
    assert not epoch.worked()

    epoch.set_status(Status.RUNNING)
    assert epoch.worked() and epoch.claimed()

    epoch.set_status(Status.INTERRUPTED)
    assert not epoch.worked() and not epoch.claimed()


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


def test_a_claim_on_an_epoch_still_waiting_is_written_again_too(
    epoch: EpochStore, beats: _Beats
) -> None:
    """A worker claims first, and may be seconds from saying it runs."""
    assert epoch.claim()

    assert beats.wake(beats.newest())

    assert epoch.worked()
    epoch.set_status(Status.FINISHED)


def test_a_thread_left_by_an_earlier_test_is_not_taken_for_this_ones() -> None:
    """An earlier test's thread in this process, going to sleep once more on its
    way to its end, would have been woken in place of the one a test means."""
    start = threading.Event()
    held: list[_Beats] = []

    def left_behind() -> None:
        start.wait(WAIT_S)
        held[0].sleep(0.0)

    thread = threading.Thread(target=left_behind, daemon=True)
    thread.start()
    held.append(_Beats())

    start.set()
    thread.join(WAIT_S / 10)

    assert not thread.is_alive()
    held[0].wake_all()


def test_a_claim_taken_on_an_epoch_that_had_ended_is_held_until_it_is_let_go(
    epoch: EpochStore, beats: _Beats
) -> None:
    """A resume asked of an epoch interrupted holds it so while it makes ready: that
    status says nothing of the holder, which has not ended anything yet."""
    epoch.set_status(Status.INTERRUPTED)
    assert epoch.claim()
    thread = beats.newest()

    assert beats.wake(thread)

    assert epoch.claimed() and epoch.worked()
    assert not EpochStore(epoch.objects, "run", 0).claim()

    # Once it has said the epoch waits, what ends it ends the claim, as for any other.
    epoch.queue_again(scenario_file=None, seconds_per_day=None)
    assert beats.wake(thread)
    ended = epoch.manifest().model_copy(update={"status": Status.INTERRUPTED})
    epoch.objects.put("run/0/manifest.json", ended.model_dump_json().encode())
    assert not beats.wake(thread)
    assert not epoch.worked()


def test_a_resume_making_ready_for_longer_than_a_beat_keeps_the_epoch_its_own(
    tmp_path: Path, beats: _Beats, monkeypatch: pytest.MonkeyPatch
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        made.runs = objects
        kept = workers.queued(made, objects, workers_support.SHORT)
        assert workers.execute(made, kept, workers.Stepped([DAY_S])) == Status.INTERRUPTED
        # The thread of the claim it let go, which is not the one this test wakes.
        beats.newest()
        another = EpochStore(objects, kept.run_id, kept.epoch)
        taken = []

        def restores_slowly(*args: Any) -> Any:
            assert beats.wake(beats.newest())
            taken.append(another.claim())
            return upload_checkpoint(*args)

        monkeypatch.setattr(workers, "upload_checkpoint", restores_slowly)
        resumed = EpochStore(objects, kept.run_id, kept.epoch)

        assert workers.resume(made, resumed, workers.Free()) == Status.FINISHED

    assert taken == [False]
    assert len(kept.commits()) == workers_support.SHORT_DAYS
    kept.verify()


def test_an_epoch_told_it_ended_by_another_process_is_let_go_by_the_thread(
    epoch: EpochStore, beats: _Beats
) -> None:
    epoch.set_status(Status.RUNNING)
    # Said to have ended by a process stopped before it let go: this one's thread
    # must not go on holding it.
    ended = epoch.manifest().model_copy(update={"status": Status.INTERRUPTED})
    epoch.objects.put(
        f"{epoch.run_id}/{epoch.epoch}/manifest.json", ended.model_dump_json().encode()
    )
    assert epoch.worked()

    assert not beats.wake(beats.newest())

    assert not epoch.worked()


def test_a_lease_that_is_not_one_is_not_believed(epoch: EpochStore) -> None:
    epoch.objects.put(f"{epoch.run_id}/{epoch.epoch}/{leases.CLAIMS}/00000000.json", b"not json")

    assert not epoch.worked()
    assert epoch.claim()
    epoch.let_go()


def test_a_thread_that_wakes_on_an_epoch_queued_again_leaves_it_free_for_a_worker(
    epoch: EpochStore, beats: _Beats
) -> None:
    epoch.set_status(Status.RUNNING)
    old = beats.newest()
    _ended_and_queued(epoch)

    assert not beats.wake(old)

    assert not epoch.worked()
    assert workers.check_resumable(epoch) == 0.0


def test_a_thread_that_wakes_on_a_new_holders_lease_leaves_it_as_it_is(
    epoch: EpochStore, beats: _Beats
) -> None:
    epoch.set_status(Status.RUNNING)
    old = beats.newest()
    _ended_and_queued(epoch)
    epoch.set_status(Status.RUNNING)
    new = beats.newest()
    theirs = epoch.objects.get(_claim(epoch))

    assert not beats.wake(old)
    assert epoch.objects.get(_claim(epoch)) == theirs

    # And the new holder is not put off by it.
    assert beats.wake(new)
    assert epoch.claimed()
    assert theirs is not None and _refreshed_at(epoch) >= json.loads(theirs)["refreshed_at"]


def test_a_thread_stopped_before_its_write_takes_nothing_from_the_holder_after_it(
    tmp_path: Path, beats: _Beats
) -> None:
    objects = _Stopped(tmp_path)
    first = EpochStore.create(objects, _manifest())
    second = EpochStore(FolderStore(tmp_path), "run", 0)
    first.set_status(Status.RUNNING)
    old = beats.newest()

    def ended_and_taken_by_another() -> None:
        _ended_and_queued(second)
        second.set_status(Status.RUNNING)

    objects.before = ended_and_taken_by_another

    # It has written, too late, and looks again at its next beat.
    beats.wake(old)
    new = beats.newest()
    assert not beats.wake(old)

    assert beats.wake(new)
    assert second.worked()
    second.set_status(Status.FINISHED)


@pytest.mark.parametrize(
    "told",
    [lambda epoch: epoch.set_status(Status.INTERRUPTED), _ended_and_queued],
    ids=["ended", "ended and queued again"],
)
@pytest.mark.parametrize("when", ["before", "after"])
def test_an_epoch_that_ends_as_its_claim_is_written_is_left_with_none_believed(
    tmp_path: Path, beats: _Beats, told: Callable[[EpochStore], None], when: str
) -> None:
    objects = _Stopped(tmp_path)
    epoch = EpochStore.create(objects, _manifest())
    epoch.set_status(Status.RUNNING)
    thread = beats.newest()
    setattr(objects, when, lambda: told(EpochStore(FolderStore(tmp_path), "run", 0)))

    beats.wake(thread)

    assert not epoch.worked()
    assert not beats.wake(thread)
    assert not epoch.worked()


def test_a_thread_finding_its_epoch_ended_does_not_let_go_of_a_claim_another_has_taken(
    tmp_path: Path, beats: _Beats
) -> None:
    objects = _Stopped(tmp_path)
    epoch = EpochStore.create(objects, _manifest())
    epoch.set_status(Status.RUNNING)
    thread = beats.newest()
    another = EpochStore(FolderStore(tmp_path), "run", 0)

    def taken_over() -> None:
        written = json.loads(epoch.objects.get(_claim(epoch)) or b"{}")["refreshed_at"]
        assert another.claim(now=written + leases.EXPIRES_AFTER_S + 1)

    # Ended by a process stopped before it let go, and claimed as the thread lets go.
    ended = epoch.manifest().model_copy(update={"status": Status.INTERRUPTED})
    objects.put("run/0/manifest.json", ended.model_dump_json().encode())
    objects.before = taken_over

    assert not beats.wake(thread)

    assert another.claimed() and another.worked()
    another.let_go()


def test_a_lease_from_before_claims_is_believed_and_goes_when_the_epoch_is_let_go(
    epoch: EpochStore,
) -> None:
    written = time.time()
    old_format = json.dumps({"refreshed_at": written}).encode()
    epoch.objects.put(_old_lease(epoch), old_format)

    assert epoch.worked(now=written + leases.EXPIRES_AFTER_S)
    assert not epoch.worked(now=written + leases.EXPIRES_AFTER_S + 1)

    # An epoch that is carried on from it is refused while it is believed.
    epoch.set_status(Status.INTERRUPTED)
    epoch.objects.put(_old_lease(epoch), old_format)
    with pytest.raises(Conflict, match="worked by a process still"):
        workers.check_resumable(epoch)
    assert not epoch.claim()
    # And not after it has expired.
    assert epoch.claim(now=written + leases.EXPIRES_AFTER_S + 1)

    epoch.set_status(Status.FINISHED)
    assert epoch.objects.get(_old_lease(epoch)) is None


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
            assert not epoch.worked()
        finally:
            scheduling.close()
