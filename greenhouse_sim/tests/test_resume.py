"""An interrupted epoch is carried on (P17.9, decision 0065): the same epoch,
from the checkpoint of its last commit, ending as the epoch that was never
interrupted does, whatever a crash left past its last commit."""

import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import interrupted, leases
from greenhouse_sim.services.checkpoints import checkpoints
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.run_store import (
    EpochStore,
    FolderStore,
    LogEntry,
    Status,
    StoreCorrupt,
    instant_name,
)
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Paced, Stepped, execute, queued, resume

sys.path.insert(0, str(Path(__file__).parent))

import short_runs

SHORT: Final = "climate_box_short"
DAYS: Final = 3
WAIT_S: Final = 60.0


def _simulator() -> Simulator:
    """A run of three days of the one-plant box; a new one is a process started
    again, which keeps none of what the one before worked out."""
    made = Simulator()
    made.catalogue.register(short_runs.one_plant_box(SHORT, DAYS))
    return made


@pytest.fixture
def simulator() -> Iterator[Simulator]:
    with _simulator() as made:
        yield made


def _epoch(simulator: Simulator, root: Path) -> EpochStore:
    return queued(simulator, FolderStore(root), SHORT)


def _digests(epoch: EpochStore) -> list[str]:
    return [commit.digest for commit in epoch.commits()]


@pytest.fixture(scope="module")
def uninterrupted(tmp_path_factory: pytest.TempPathFactory) -> EpochStore:
    """The epoch that was never interrupted, to end."""
    with _simulator() as simulator:
        epoch = _epoch(simulator, tmp_path_factory.mktemp("whole"))
        assert execute(simulator, epoch, Free()) == Status.FINISHED
        return epoch


def _interrupted_after(simulator: Simulator, root: Path, days: int) -> EpochStore:
    """An epoch of the same run that stopped after `days` days."""
    epoch = _epoch(simulator, root)
    barriers = [(day + 1) * DAY_S for day in range(days)]
    assert execute(simulator, epoch, Stepped(barriers)) == Status.INTERRUPTED
    assert len(epoch.commits()) == days
    return epoch


def test_a_resumed_epoch_is_the_epoch_that_was_never_interrupted(
    tmp_path: Path, uninterrupted: EpochStore
) -> None:
    with _simulator() as before:
        epoch = _interrupted_after(before, tmp_path, 1)
    # A process started again, which has worked out none of it.
    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED
        restored = [c.day for c in checkpoints(after)]

    assert restored == [1]
    assert _digests(epoch) == _digests(uninterrupted)
    assert epoch.manifest().status == Status.FINISHED
    assert [o.model_dump_json() for o in epoch.observations().records] == [
        o.model_dump_json() for o in uninterrupted.observations().records
    ]
    epoch.verify()


def test_a_run_for_fewer_days_resumes_to_its_own_end_as_the_whole_runs_first_days(
    tmp_path: Path, uninterrupted: EpochStore
) -> None:
    """Decision 0075: a run cut short is its scenario's run, ended sooner."""
    with _simulator() as before:
        epoch = queued(before, FolderStore(tmp_path), SHORT, duration_days=DAYS - 1)
        assert execute(before, epoch, Stepped([DAY_S])) == Status.INTERRUPTED
    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    assert epoch.run_id == uninterrupted.run_id
    assert epoch.frontier_s() == (DAYS - 1) * DAY_S
    assert _digests(epoch) == _digests(uninterrupted)[: DAYS - 1]


def test_an_epoch_with_nothing_committed_begins_again(
    tmp_path: Path, uninterrupted: EpochStore
) -> None:
    with _simulator() as before:
        epoch = _interrupted_after(before, tmp_path, 0)
    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    assert _digests(epoch) == _digests(uninterrupted)


def test_only_an_interrupted_epoch_resumes(simulator: Simulator, tmp_path: Path) -> None:
    finished = _epoch(simulator, tmp_path)
    assert execute(simulator, finished, Free()) == Status.FINISHED

    with pytest.raises(Conflict, match="only an interrupted one resumes"):
        resume(simulator, finished, Free())
    assert finished.manifest().status == Status.FINISHED


def test_an_epoch_whose_last_commit_keeps_no_checkpoint_is_refused(
    simulator: Simulator, tmp_path: Path
) -> None:
    epoch = _interrupted_after(simulator, tmp_path, 1)
    epoch.commit(DAY_S, 2 * DAY_S)
    epoch.set_status(Status.INTERRUPTED)

    with pytest.raises(Conflict, match="no checkpoint"):
        resume(simulator, epoch, Free())


def test_a_stepped_epoch_is_carried_on_by_its_caller(simulator: Simulator, tmp_path: Path) -> None:
    epoch = _interrupted_after(simulator, tmp_path, 1)

    with pytest.raises(InvalidRequest, match="by that caller"):
        resume(simulator, epoch, Stepped([2 * DAY_S]))


def test_an_epoch_whose_last_commit_is_not_what_it_names_is_not_carried_on(
    simulator: Simulator, tmp_path: Path
) -> None:
    epoch = _interrupted_after(simulator, tmp_path, 2)
    last = epoch.commits()[-1]
    path = tmp_path / last.checkpoint if last.checkpoint else tmp_path
    path.write_bytes(path.read_bytes() + b"x")

    with pytest.raises(StoreCorrupt):
        resume(simulator, epoch, Free())
    assert epoch.manifest().status == Status.INTERRUPTED


class Crash(BaseException):
    """The process dying: not an error any handler of the epoch's catches."""


class CrashingStore(FolderStore):
    """A folder store whose process dies as it writes the `skip + 1`th object
    whose name holds `pattern`, once."""

    def __init__(self, root: Path, pattern: str, *, skip: int = 0) -> None:
        super().__init__(root)
        self._pattern = pattern
        self._skip = skip

    def put(self, name: str, data: bytes) -> None:
        if self._pattern in name:
            if self._skip == 0:
                self._pattern = "\0"
                raise Crash(name)
            self._skip -= 1
        super().put(name, data)


def _crashed(pattern: str, root: Path, *, skip: int) -> EpochStore:
    """An epoch whose process died as it wrote `pattern`, that a simulator
    started again finds `running` with no one to work it."""
    store = CrashingStore(root, pattern, skip=skip)
    with _simulator() as before:
        epoch = queued(before, store, SHORT)
        with pytest.raises(Crash):
            execute(before, epoch, Free())
    assert epoch.manifest().status == Status.RUNNING
    return epoch


def _held(epoch: EpochStore) -> set[str]:
    return set(epoch.objects.names(f"{epoch.run_id}/{epoch.epoch}/"))


def _second_day_is_held(epoch: EpochStore) -> bool:
    """Whether a segment of the second day is there, which no commit names."""
    span = f"segments/{instant_name(DAY_S)}-{instant_name(2 * DAY_S)}/"
    return any(span in name for name in _held(epoch))


def _carried_on(epoch: EpochStore) -> None:
    """The epoch found, and carried on, by a simulator started again."""
    with _simulator() as after:
        after.runs = epoch.objects
        later = time.time() + leases.EXPIRES_AFTER_S * 2
        (found,) = interrupted.mark(after, now=later)
        assert (found.run_id, found.epoch) == (epoch.run_id, epoch.epoch)
        assert resume(after, epoch, Free()) == Status.FINISHED


def test_a_crash_between_the_log_and_the_commit_leaves_a_segment_that_is_written_again(
    tmp_path: Path, uninterrupted: EpochStore
) -> None:
    # The second commit's segment and checkpoint are written; its file, which
    # names them, is not.
    epoch = _crashed("commits/00000001", tmp_path, skip=0)
    assert len(epoch.commits()) == 1
    assert _second_day_is_held(epoch)

    _carried_on(epoch)

    assert _digests(epoch) == _digests(uninterrupted)
    epoch.verify()


def test_a_crash_as_a_checkpoint_is_written_leaves_a_segment_that_no_commit_names(
    tmp_path: Path, uninterrupted: EpochStore
) -> None:
    epoch = _crashed("checkpoints/", tmp_path, skip=1)
    assert len(epoch.commits()) == 1
    assert _second_day_is_held(epoch)

    _carried_on(epoch)

    assert _digests(epoch) == _digests(uninterrupted)
    epoch.verify()


def test_an_epoch_whose_final_day_is_committed_is_finished_not_driven_again(
    tmp_path: Path, uninterrupted: EpochStore
) -> None:
    # The process dies as the epoch is told it finished, the third write of
    # its manifest: every day is committed, and the status says running.
    epoch = _crashed("manifest.json", tmp_path, skip=2)
    assert len(epoch.commits()) == DAYS

    _carried_on(epoch)

    assert epoch.manifest().status == Status.FINISHED
    assert _digests(epoch) == _digests(uninterrupted)


def test_an_epoch_whose_final_day_is_committed_is_finished_at_a_pace_too(
    tmp_path: Path, uninterrupted: EpochStore
) -> None:
    epoch = _crashed("manifest.json", tmp_path, skip=2)
    # A resume that would wait for a day to pass is ended, and the test failed.
    stop = threading.Event()
    timer = threading.Timer(WAIT_S, stop.set)
    timer.start()
    try:
        with _simulator() as after:
            after.runs = epoch.objects
            interrupted.mark(after, now=time.time() + leases.EXPIRES_AFTER_S * 2)
            assert resume(after, epoch, Paced(1.0), stop=stop) == Status.FINISHED
    finally:
        timer.cancel()

    assert not stop.is_set()
    assert _digests(epoch) == _digests(uninterrupted)


def test_what_a_crash_left_past_the_last_commit_is_removed_before_it_is_carried_on(
    tmp_path: Path,
) -> None:
    with _simulator() as simulator:
        epoch = _interrupted_after(simulator, tmp_path, 1)
        home = f"{epoch.run_id}/{epoch.epoch}"
        before = _held(epoch)
        # A segment and a checkpoint for a span no commit has, a commit past a
        # gap; and a log entry given after the last commit, with the request it
        # came by, which are not to be lost.
        orphans = {
            f"{home}/segments/{'9' * 16}-{'9' * 16}/events.parquet",
            f"{home}/checkpoints/{'9' * 16}.json.zst",
            f"{home}/commits/00000007.json",
        }
        for name in orphans:
            epoch.objects.put(name, b"left by a crash")
        entry = LogEntry(seq=0, at_s=DAY_S, given_s=DAY_S, by="someone", what={})
        epoch.append_log(entry)
        request = epoch.ask({"kind": "targets", "targets": {}})

        removed = epoch.discard_uncommitted()

        assert orphans <= set(removed)
        assert _held(epoch) == before | {
            f"{home}/interventions.jsonl",
            f"{home}/requests/{request}.json",
        }
        assert epoch.logged() == [entry]


def test_a_request_asked_as_the_epoch_is_tidied_up_is_not_removed(tmp_path: Path) -> None:
    """The asker is in another process, and may ask between any two listings."""

    class AskingWhileListing(FolderStore):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.asked: list[str] = []
            self.epoch: EpochStore | None = None

        def names(self, prefix: str = "") -> list[str]:
            # As the epoch's whole folder is listed, whatever was listed before.
            if self.epoch is not None and prefix == f"{self.epoch.run_id}/{self.epoch.epoch}/":
                self.asked.append(self.epoch.ask({"kind": "targets", "targets": {}}))
            return super().names(prefix)

    with _simulator() as simulator:
        store = AskingWhileListing(tmp_path)
        epoch = _epoch(simulator, tmp_path)
        again = EpochStore(store, epoch.run_id, epoch.epoch)
        store.epoch = again

        again.discard_uncommitted()

    assert again.requests() == store.asked
