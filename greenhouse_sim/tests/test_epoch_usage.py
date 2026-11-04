"""An epoch says what it used and why it failed (P18.2, decision 0067): a report
beside its manifest at each commit, in no digest, which the list reads instead
of walking; what its figures mean across a resume and a fork; and a reason a
client may read."""

import errno
import json
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import forks, playback, resources, runs_kept, scheduler
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackFailed
from greenhouse_sim.services.resources import ProcessUse
from greenhouse_sim.services.run_store import (
    NO_REASON_GIVEN,
    EpochManifest,
    EpochStore,
    FolderStore,
    Status,
    StoreCorrupt,
    StoredRun,
    failure_reason,
    stored_run,
    stored_runs,
)
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Paced, Stepped, execute, queued, resume

# A worker starts from nothing and imports what it is told to run by name, so
# that the module is put where its process finds it.
sys.path.insert(0, str(Path(__file__).parent))

import workers_support

SHORT: Final = workers_support.SHORT
USAGE: Final = "usage.json"
WAIT_S: Final = 60.0
A_PATH: Final = "/Users/someone/private/runs/a"
MEBIBYTE: Final = 1024**2


@pytest.fixture
def simulator() -> Iterator[Simulator]:
    with workers_support.short_simulator() as made:
        yield made


@pytest.fixture(scope="module")
def whole(tmp_path_factory: pytest.TempPathFactory) -> EpochStore:
    """An epoch of the short run, unbroken, whose worker counted 100 s and 900
    bytes: a run's work is the time these tests take, so that they share one."""
    objects = FolderStore(tmp_path_factory.mktemp("whole"))
    with workers_support.short_simulator() as made:
        epoch = queued(made, objects, SHORT)
        epoch.counted_by(_meter(100.0, 900))
        assert execute(made, epoch, Free()) == Status.FINISHED
    return epoch


def _meter(cpu_s: float, peak: int) -> Callable[[], ProcessUse]:
    return lambda: ProcessUse(cpu_s, peak)


def _epoch(root: Path, run_id: str = "run_a", *, status: Status = Status.QUEUED) -> EpochStore:
    return EpochStore.create(
        FolderStore(root),
        EpochManifest(
            run_id=run_id,
            epoch=0,
            scenario_id="s",
            layout="default",
            status=status,
            duration_s=2 * DAY_S,
        ),
    )


def _two_days(root: Path, run_id: str = "run_a") -> EpochStore:
    store = _epoch(root, run_id)
    store.commit(0.0, DAY_S, checkpoint=b"first")
    store.commit(DAY_S, 2 * DAY_S, checkpoint=b"second")
    store.set_status(Status.FINISHED)
    return store


def _on_disk(root: Path, run_id: str = "run_a") -> int:
    """What the epoch's files hold, counted without the store's help."""
    return sum(
        path.stat().st_size
        for path in (root / run_id / "0").rglob("*")
        if path.is_file() and path.name != USAGE
    )


def _before_usage(store: EpochStore) -> None:
    """Makes an epoch what one kept before this change is: no report, and a
    manifest that does not know the field a reason is in."""
    home = f"{store.run_id}/{store.epoch}"
    store.objects.delete(f"{home}/{USAGE}")
    manifest = json.loads(store.objects.get(f"{home}/manifest.json") or b"")
    del manifest["reason"]
    store.objects.put(f"{home}/manifest.json", json.dumps(manifest).encode())


class _Counted(FolderStore):
    """A store that counts what is asked of it."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.asked: Counter[str] = Counter()
        self.got: list[str] = []

    def get(self, name: str) -> bytes | None:
        self.asked["get"] += 1
        self.got.append(name)
        return super().get(name)

    def names(self, prefix: str = "") -> list[str]:
        self.asked["names"] += 1
        return super().names(prefix)

    def size(self, name: str) -> int | None:
        self.asked["size"] += 1
        return super().size(name)


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


# What each commit reports.


def test_each_commit_reports_what_the_epoch_holds(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    assert store.usage() is None

    store.commit(0.0, DAY_S, checkpoint=b"first")
    first = store.usage()
    assert first is not None
    assert first.cpu_s is None and first.peak_memory_bytes is None, "a process that does more"
    assert (first.commits, first.checkpoints) == (1, 1)
    assert (first.frontier_s, first.days_computed) == (DAY_S, 1.0)
    assert first.bytes_kept == _on_disk(tmp_path)

    store.commit(DAY_S, 2 * DAY_S)
    second = store.usage()
    assert second is not None
    assert (second.commits, second.checkpoints) == (2, 1)
    assert (second.frontier_s, second.days_computed) == (2 * DAY_S, 2.0)
    assert second.bytes_kept == _on_disk(tmp_path) > first.bytes_kept


def test_the_report_as_an_epoch_ends_says_all_it_keeps(tmp_path: Path) -> None:
    store = _epoch(tmp_path, status=Status.RUNNING)
    store.commit(0.0, DAY_S)

    store.set_status(Status.FAILED, reason="a reason that takes up room")

    usage = store.usage()
    assert usage is not None and usage.bytes_kept == _on_disk(tmp_path)
    assert stored_runs(store.objects)[0].size_bytes == usage.bytes_kept


def test_the_report_is_in_no_digest(tmp_path: Path) -> None:
    counted = _epoch(tmp_path / "counted")
    counted.counted_by(_meter(1.0, 2))
    bare = _epoch(tmp_path / "bare")
    bare.report_usage = lambda commits=None: None  # type: ignore[method-assign]

    for store in (counted, bare):
        store.commit(0.0, DAY_S, checkpoint=b"first")
        store.commit(DAY_S, 2 * DAY_S, checkpoint=b"second")

    assert counted.usage() is not None and bare.usage() is None
    assert [c.digest for c in counted.commits()] == [c.digest for c in bare.commits()]
    counted.objects.put(f"run_a/0/{USAGE}", b'{"commits": 99, "whatever": "else"}')
    counted.verify()


def test_a_report_that_cannot_be_written_ends_nothing(tmp_path: Path) -> None:
    class Refusing(FolderStore):
        def put(self, name: str, data: bytes) -> None:
            if name.endswith(USAGE):
                raise OSError(errno.ENOSPC, "No space left on device", A_PATH)
            super().put(name, data)

    manifest = EpochManifest(run_id="run_a", epoch=0, scenario_id="s", layout="default")
    store = EpochStore.create(Refusing(tmp_path), manifest)

    made = store.commit(0.0, DAY_S)
    store.set_status(Status.FINISHED)

    assert store.commits() == [made] and store.manifest().status == Status.FINISHED
    assert store.usage() is None
    (shown,) = stored_runs(store.objects)
    assert shown.size_bytes == _on_disk(tmp_path) and shown.frontier_s == DAY_S


def test_a_report_this_build_cannot_read_fails_nothing(tmp_path: Path) -> None:
    store = _two_days(tmp_path)
    store.objects.put(f"run_a/0/{USAGE}", b'{"some": "other format"}')

    assert store.usage() is None
    (shown,) = stored_runs(store.objects)
    assert shown.frontier_s == 2 * DAY_S and shown.size_bytes == _on_disk(tmp_path)
    assert not shown.damaged


# What a resume and a fork count.


def test_a_second_worker_adds_its_seconds_and_keeps_the_highest_peak(tmp_path: Path) -> None:
    first = _epoch(tmp_path)
    first.counted_by(_meter(10.0, 300))
    first.commit(0.0, DAY_S, checkpoint=b"first")
    first.commit(DAY_S, 2 * DAY_S, checkpoint=b"second")

    second = EpochStore(first.objects, "run_a", 0)
    second.counted_by(_meter(3.0, 100))
    second.commit(2 * DAY_S, 3 * DAY_S, checkpoint=b"third")
    # Reported again, by the same worker, adds nothing more.
    second.report_usage()

    usage = second.usage()
    assert usage is not None
    assert (usage.cpu_s, usage.peak_memory_bytes) == (13.0, 300)
    assert usage.days_computed == 3.0

    third = EpochStore(first.objects, "run_a", 0)
    third.counted_by(_meter(1.0, 500))
    third.report_usage()
    usage = third.usage()
    assert usage is not None and (usage.cpu_s, usage.peak_memory_bytes) == (14.0, 500)


def test_a_writer_that_counts_nothing_keeps_what_was_counted(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    store.counted_by(_meter(10.0, 300))
    store.commit(0.0, DAY_S)

    # As the API's process tells an epoch `interrupted` when its worker is gone.
    EpochStore(store.objects, "run_a", 0).set_status(Status.INTERRUPTED)

    usage = store.usage()
    assert usage is not None and (usage.cpu_s, usage.peak_memory_bytes) == (10.0, 300)


def test_tidying_up_after_a_crash_keeps_the_report_its_next_worker_adds_to(
    tmp_path: Path,
) -> None:
    store = _epoch(tmp_path)
    store.counted_by(_meter(10.0, 300))
    store.commit(0.0, DAY_S, checkpoint=b"first")
    store.objects.put("run_a/0/checkpoints/past-the-last-commit.json.zst", b"left")

    removed = store.discard_uncommitted()

    assert removed == ["run_a/0/checkpoints/past-the-last-commit.json.zst"]
    assert store.usage() is not None


def test_a_day_a_crash_lost_is_counted_once_when_it_is_worked_again(tmp_path: Path) -> None:
    """A commit whose report was lost, and a day written and never committed:
    the days are what the commits hold, and the next report catches up."""
    store = _epoch(tmp_path)
    store.commit(0.0, DAY_S, checkpoint=b"first")
    silent = EpochStore(store.objects, "run_a", 0)
    silent.report_usage = lambda commits=None: None  # type: ignore[method-assign]
    silent.commit(DAY_S, 2 * DAY_S, checkpoint=b"second")
    behind = store.usage()
    assert behind is not None and behind.commits == 1
    store.objects.put(
        "run_a/0/segments/0000172800000000-0000259200000000/events.parquet", b"never committed"
    )

    store.discard_uncommitted()
    store.commit(2 * DAY_S, 3 * DAY_S, checkpoint=b"third")

    usage = store.usage()
    assert usage is not None
    assert (usage.commits, usage.days_computed) == (3, 3.0)
    assert usage.bytes_kept == _on_disk(tmp_path)


def test_an_epoch_carried_on_says_the_whole_of_what_it_used_with_the_digests_of_one_unbroken(
    simulator: Simulator, tmp_path: Path, whole: EpochStore
) -> None:
    broken = queued(simulator, FolderStore(tmp_path), SHORT)
    broken.counted_by(_meter(10.0, 300))
    assert execute(simulator, broken, Stepped([DAY_S])) == Status.INTERRUPTED
    told = broken.usage()
    assert told is not None and (told.days_computed, told.cpu_s) == (1.0, 10.0)
    again = EpochStore(broken.objects, broken.run_id, broken.epoch)
    again.counted_by(_meter(4.0, 100))
    assert resume(simulator, again, Free()) == Status.FINISHED

    usage = again.usage()
    assert usage is not None
    assert (usage.days_computed, usage.cpu_s, usage.peak_memory_bytes) == (2.0, 14.0, 300)
    assert usage.bytes_kept == _on_disk(tmp_path, again.run_id)
    # What was reported moved no id and no digest.
    assert again.run_id == whole.run_id
    assert [c.digest for c in again.commits()] == [c.digest for c in whole.commits()]


def test_a_fork_counts_from_what_it_inherits_and_none_of_its_parents_use(
    simulator: Simulator, whole: EpochStore
) -> None:
    objects = whole.objects
    made = forks.fork(simulator, objects, whole.run_id, whole.epoch, DAY_S)

    # Asked for, it holds the state it inherits and has computed nothing.
    waiting = stored_run(objects, made.run_id, made.epoch)
    assert waiting.size_bytes > 0 and waiting.days_computed == 0.0
    assert waiting.cpu_s is None and waiting.peak_memory_bytes is None
    in_list = next(r for r in stored_runs(objects) if r.epoch == made.epoch)
    assert in_list == waiting

    made.counted_by(_meter(4.0, 100))
    assert resume(simulator, made, Free()) == Status.FINISHED

    usage = made.usage()
    assert usage is not None
    assert (usage.days_computed, usage.frontier_s) == (1.0, 2 * DAY_S)
    assert (usage.cpu_s, usage.peak_memory_bytes) == (4.0, 100)
    assert usage.checkpoints == 2, "what it inherits and what it made"
    assert next(r for r in stored_runs(objects) if r.epoch == made.epoch).cpu_s == 4.0
    assert not stored_run(objects, made.run_id, made.epoch).damaged
    assert usage.bytes_kept == sum(
        objects.size(name) or 0
        for name in objects.names(f"{made.run_id}/{made.epoch}/")
        if not name.endswith(USAGE)
    )


def test_a_worker_counts_its_own_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """What `work` runs is the epoch and nothing else, and so counts itself."""

    def one_commit(_: Simulator, kept: EpochStore, __: object) -> Status:
        kept.commit(0.0, DAY_S)
        kept.set_status(Status.FINISHED)
        return Status.FINISHED

    monkeypatch.setattr(scheduler, "carry_on", one_commit)
    store = _epoch(tmp_path)

    with pytest.raises(SystemExit) as ended:
        scheduler.work(str(tmp_path), store.run_id, store.epoch)

    assert ended.value.code == 0
    (shown,) = stored_runs(store.objects)
    assert shown.cpu_s is not None and shown.cpu_s > 0
    assert shown.peak_memory_bytes is not None and shown.peak_memory_bytes > MEBIBYTE


# What a list reads.


def test_a_list_reads_each_report_and_walks_nothing(tmp_path: Path) -> None:
    for run_id in ("run_a", "run_b"):
        _two_days(tmp_path, run_id)
    objects = _Counted(tmp_path)

    found = stored_runs(objects)

    assert objects.asked == {"get": 2 * 2}, "a manifest and a report each"
    assert not [name for name in objects.got if "/commits/" in name]
    assert [r.frontier_s for r in found] == [2 * DAY_S, 2 * DAY_S]
    assert [r.size_bytes for r in found] == [_on_disk(tmp_path, r.run_id) for r in found]


def test_a_list_says_of_an_epoch_what_opening_it_says(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    store.counted_by(_meter(10.0, 300))
    store.commit(0.0, DAY_S, checkpoint=b"first")
    store.set_status(Status.FAILED, reason="it had a reason")

    (listed,) = stored_runs(store.objects)

    assert listed == stored_run(store.objects, "run_a", 0)
    assert (listed.cpu_s, listed.peak_memory_bytes) == (10.0, 300)
    assert listed.days_computed == 1.0 and listed.reason == "it had a reason"
    assert listed.progress == 0.5


def test_a_list_by_scenario_reads_only_the_manifest_of_another(tmp_path: Path) -> None:
    _two_days(tmp_path)
    objects = _Counted(tmp_path)

    assert stored_runs(objects, "another scenario") == []

    assert objects.got == ["run_a/0/manifest.json"]


def test_an_epoch_from_before_reports_is_listed_by_walking_it_with_what_can_be_known(
    tmp_path: Path,
) -> None:
    store = _two_days(tmp_path)
    expected = stored_run(store.objects, "run_a", 0)
    _before_usage(store)
    size = _on_disk(tmp_path)
    objects = _Counted(tmp_path)

    (shown,) = stored_runs(objects)

    assert shown.status == Status.FINISHED and shown.reason is None
    assert (shown.frontier_s, shown.days_computed) == (2 * DAY_S, 2.0)
    assert shown.size_bytes == size
    assert shown.cpu_s is None and shown.peak_memory_bytes is None
    assert not shown.damaged
    assert shown.model_dump(exclude={"size_bytes"}) == expected.model_dump(exclude={"size_bytes"})
    # Its cost: each commit read and each object's size asked for.
    assert [name for name in objects.got if "/commits/" in name]
    assert objects.asked["size"] == len(store.objects.names("run_a/0/"))


def test_an_epoch_from_before_reports_that_is_carried_on_reports_from_then_on(
    tmp_path: Path,
) -> None:
    """Its days and bytes are all of them; its seconds only those counted."""
    store = _two_days(tmp_path)
    _before_usage(store)

    again = EpochStore(store.objects, "run_a", 0)
    again.counted_by(_meter(4.0, 100))
    again.commit(2 * DAY_S, 3 * DAY_S)

    usage = again.usage()
    assert usage is not None
    assert (usage.days_computed, usage.cpu_s) == (3.0, 4.0)
    assert usage.bytes_kept == _on_disk(tmp_path)


def test_a_commit_whose_report_a_crash_lost_is_listed_all_the_same(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    store.counted_by(_meter(10.0, 300))
    store.commit(0.0, DAY_S)
    silent = EpochStore(store.objects, "run_a", 0)
    silent.report_usage = lambda commits=None: None  # type: ignore[method-assign]
    silent.commit(DAY_S, 2 * DAY_S)

    (shown,) = stored_runs(store.objects)

    assert shown.frontier_s == 2 * DAY_S and shown.days_computed == 2.0
    assert shown.size_bytes == _on_disk(tmp_path)
    assert shown.cpu_s == 10.0, "as far as it last reported"
    assert not shown.damaged


@pytest.mark.parametrize(
    "lost",
    [
        "commits/00000000.json",
        "checkpoints/0000086400000000.json.zst",
        "segments/0000000000000000-0000086400000000/events.parquet",
    ],
)
def test_what_is_lost_from_a_folder_it_counts_is_seen_by_a_list(tmp_path: Path, lost: str) -> None:
    store = _two_days(tmp_path)
    objects = store.objects
    if lost.startswith("segments/"):
        # The whole of a day's folder: what a list can count.
        for name in objects.names(f"run_a/0/{Path(lost).parent}/"):
            objects.delete(name)
        (tmp_path / "run_a/0" / Path(lost).parent).rmdir()
    else:
        objects.delete(f"run_a/0/{lost}")

    (shown,) = stored_runs(objects)

    assert shown.damaged


def test_a_file_lost_from_a_days_folder_is_seen_when_the_epoch_is_opened(
    tmp_path: Path,
) -> None:
    """A list counts folders and does not look in each. The limit of what it
    says: opening the epoch looks at its objects, and refuses it in words, in
    place of a read that fails where it comes to the gap."""
    store = _two_days(tmp_path)
    objects = store.objects
    objects.delete("run_a/0/segments/0000000000000000-0000086400000000/events.parquet")

    assert not stored_runs(objects)[0].damaged
    assert stored_run(objects, "run_a", 0).damaged

    with Simulator(runs=objects) as simulator:
        with pytest.raises(Conflict, match="files of run run_a, epoch 0 are missing"):
            runs_kept.open_position(simulator, "run_a", 0)
        answered = respond(simulator, "POST", "/api/runs/run_a/epochs/0/positions")
        assert answered.status == HTTPStatus.CONFLICT


def test_a_last_commit_lost_is_an_epoch_at_the_commit_before_as_a_crash_leaves_one(
    tmp_path: Path,
) -> None:
    store = _two_days(tmp_path)
    store.objects.delete("run_a/0/commits/00000001.json")

    (shown,) = stored_runs(store.objects)

    assert shown.frontier_s == DAY_S and shown == stored_run(store.objects, "run_a", 0)


def test_a_list_answers_with_what_was_used_over_the_api(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    store.counted_by(_meter(10.0, 300))
    store.commit(0.0, DAY_S)
    store.set_status(Status.FAILED, reason="it had a reason")

    with Simulator(runs=store.objects) as simulator:
        answered = respond(simulator, "GET", "/api/runs")
        one = respond(simulator, "GET", "/api/runs/run_a/epochs/0")

    assert answered.status == HTTPStatus.OK and isinstance(answered.body, list)
    (shown,) = answered.body
    assert isinstance(shown, dict)
    assert shown["cpu_s"] == 10.0 and shown["peak_memory_bytes"] == 300
    assert shown["days_computed"] == 1.0 and shown["reason"] == "it had a reason"
    assert one.body == shown


# Why an epoch failed.


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (MemoryError(), "its worker ran out of memory"),
        (OSError(errno.ENOSPC, "No space left", A_PATH), "the disk of its run store is full"),
        (
            OSError(errno.EACCES, "Permission denied", A_PATH),
            "its run store could not be read or written (EACCES)",
        ),
        (
            StoreCorrupt(f"{A_PATH} is gone"),
            "an object its commits name is missing, or is not what its digest says",
        ),
        (ValueError(f"at {A_PATH}: 3.5"), "its run could not be worked out (ValueError)"),
        (Conflict("a sentence for a client"), "a sentence for a client"),
    ],
)
def test_a_reason_says_the_kind_of_a_failure_and_none_of_its_text(
    error: Exception, reason: str
) -> None:
    assert failure_reason(error) == reason


def test_a_reason_is_that_of_what_a_playback_failed_for(tmp_path: Path) -> None:
    try:
        try:
            raise OSError(errno.ENOSPC, "No space left", A_PATH)
        except OSError as cause:
            raise PlaybackFailed("run_a") from cause
    except PlaybackFailed as failed:
        assert failure_reason(failed) == "the disk of its run store is full"


@pytest.mark.parametrize("driver", [Free(), Paced(seconds_per_day=0.01)], ids=["free", "paced"])
def test_an_epoch_whose_simulation_fails_says_why_and_no_more_than_that(
    simulator: Simulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    driver: Free | Paced,
) -> None:
    _fails_at_once(monkeypatch)
    epoch = queued(simulator, FolderStore(tmp_path), SHORT)

    assert execute(simulator, epoch, driver) == Status.FAILED

    assert epoch.manifest().reason == "its run could not be worked out (RuntimeError)"
    (shown,) = stored_runs(epoch.objects)
    assert shown.reason == epoch.manifest().reason
    held = (tmp_path / epoch.run_id / "0" / "manifest.json").read_text()
    assert A_PATH not in held and "Traceback" not in held and A_PATH not in shown.model_dump_json()


def _fails_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(sim: Simulator, run: RunRequest, *args: Any, **kw: Any) -> Any:
        raise RuntimeError(f"a failure at {A_PATH}")

    monkeypatch.setattr(playback, "delivered_between", failing)


def test_a_playback_in_the_apis_process_says_why_its_epoch_failed(
    simulator: Simulator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no worker around it: only its own thread says how the epoch ended."""
    _fails_at_once(monkeypatch)
    epochs = Epochs(tmp_path)
    run = Playback(simulator, SHORT, epochs=epochs)

    run.begin()
    try:
        _until(lambda: stored_runs(epochs.objects)[0].status == Status.FAILED, "the epoch's end")
    finally:
        run.stop()

    assert stored_runs(epochs.objects)[0].reason == "its run could not be worked out (RuntimeError)"


def test_a_failure_found_when_a_day_is_kept_says_why_its_epoch_failed(
    simulator: Simulator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fails_at_once(monkeypatch)
    epochs = Epochs(tmp_path)
    run = Playback(simulator, SHORT, epochs=epochs)

    assert not run.work_day(0)
    run.keep()

    (shown,) = stored_runs(epochs.objects)
    assert shown.status == Status.FAILED
    assert shown.reason == "its run could not be worked out (RuntimeError)"


def test_an_epoch_whose_disk_fills_says_so_without_its_path(
    simulator: Simulator, tmp_path: Path
) -> None:
    class Full(FolderStore):
        def put(self, name: str, data: bytes) -> None:
            if name.endswith(".parquet"):
                raise OSError(errno.ENOSPC, "No space left on device", str(self.root / name))
            super().put(name, data)

    epoch = queued(simulator, Full(tmp_path), SHORT)

    assert execute(simulator, epoch, Free()) == Status.FAILED

    assert epoch.manifest().reason == "the disk of its run store is full"
    assert str(tmp_path) not in stored_runs(epoch.objects)[0].model_dump_json()


def test_every_failure_has_a_reason_and_only_a_failure_keeps_one(tmp_path: Path) -> None:
    store = _epoch(tmp_path, status=Status.RUNNING)

    store.set_status(Status.FAILED)
    assert store.manifest().reason == NO_REASON_GIVEN

    store.set_status(Status.FAILED, reason="it had a reason")
    assert store.manifest().reason == "it had a reason"

    store.queue_again(scenario_file=None, seconds_per_day=None)
    assert store.manifest().reason is None

    store.set_status(Status.FAILED, reason="again")
    store.set_status(Status.INTERRUPTED, reason="not one to keep")
    assert store.manifest().reason is None


def test_an_epoch_whose_lease_expired_is_interrupted_with_no_reason_and_what_it_counted(
    tmp_path: Path,
) -> None:
    """A worker killed outright wrote nothing: its lease expires, and it is not
    `failed`, which would say someone knew why."""
    store = EpochStore.create(
        FolderStore(tmp_path),
        EpochManifest(
            run_id="run_a",
            epoch=0,
            scenario_id="s",
            layout="default",
            status=Status.RUNNING,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )
    store.counted_by(_meter(10.0, 300))
    store.commit(0.0, DAY_S)

    with Simulator(runs=store.objects):
        (shown,) = stored_runs(store.objects)

    assert shown.status == Status.INTERRUPTED and shown.reason is None
    assert shown.cpu_s == 10.0 and shown.days_computed == 1.0


@pytest.mark.parametrize(
    ("worker", "expected"),
    [
        (workers_support.takes_it_up_and_is_killed, (Status.INTERRUPTED, None)),
        (
            workers_support.ends_at_once,
            (Status.FAILED, "its worker ended with 1 before it began"),
        ),
    ],
    ids=["killed", "ended_before_it_began"],
)
def test_what_a_scheduler_says_of_a_worker_gone_without_a_word(
    simulator: Simulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worker: Callable[[str, str, int], None],
    expected: tuple[Status, str | None],
) -> None:
    objects = FolderStore(tmp_path)
    simulator.runs = objects
    monkeypatch.setattr(scheduler, "work", worker)
    made = Scheduler(simulator, tmp_path, limit=1)
    try:
        shown = made.start(SHORT)
        epoch = EpochStore(objects, shown.run_id, shown.epoch)
        _until(lambda: epoch.manifest().status in (Status.INTERRUPTED, Status.FAILED), "its end")
    finally:
        made.close()

    assert (epoch.manifest().status, epoch.manifest().reason) == expected


# What a process has used.


@pytest.mark.parametrize(
    ("platform", "expected"),
    [("darwin", 1024), ("linux", 1024 * 1024), ("freebsd14", 1024 * 1024)],
)
def test_peak_memory_is_in_bytes_on_each_platform(platform: str, expected: int) -> None:
    assert resources.maxrss_bytes(1024, platform) == expected


def test_linuxs_high_water_mark_is_read_in_bytes() -> None:
    status = "Name:\tpython\nVmPeak:\t  900 kB\nVmHWM:\t   2048 kB\nVmRSS:\t  1024 kB\n"

    assert resources.high_water_bytes(status) == 2048 * 1024
    assert resources.high_water_bytes("Name:\tpython\n") is None


def test_this_machine_says_a_peak_of_the_right_size() -> None:
    """Not a thousand times off, either way, on the platform this runs on."""
    used = resources.this_process()
    resident_kib = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True, check=True
    ).stdout

    assert used.cpu_s > 0
    machine = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    assert int(resident_kib) * 1024 / 2 <= used.peak_memory_bytes <= machine


PARENT_THEN_CHILD: Final = """
import subprocess, sys
from greenhouse_sim.services.resources import peak_memory_bytes
held = b"x" * (256 * 1024 * 1024)
child = subprocess.run(
    [sys.executable, "-c",
     "from greenhouse_sim.services.resources import peak_memory_bytes;"
     "print(peak_memory_bytes())"],
    capture_output=True, text=True, check=True,
)
print(peak_memory_bytes(), child.stdout.strip())
"""


@pytest.mark.skipif(sys.platform != "linux", reason="`ru_maxrss` outlives an exec only on Linux")
def test_a_worker_is_not_told_the_peak_of_the_process_that_started_it() -> None:
    answered = subprocess.run(
        [sys.executable, "-c", PARENT_THEN_CHILD], capture_output=True, text=True, check=True
    ).stdout

    parent, child = (int(figure) for figure in answered.split())

    assert parent >= 256 * MEBIBYTE > child


def test_a_stored_run_as_the_schema_reads_it_says_none_for_what_it_does_not_know(
    tmp_path: Path,
) -> None:
    """The answer's fields, for an epoch only just asked for."""
    store = _epoch(tmp_path)

    (shown,) = stored_runs(store.objects)

    assert StoredRun.model_validate(shown.model_dump()) == shown
    assert shown.cpu_s is None and shown.peak_memory_bytes is None
    assert shown.days_computed == 0.0 and shown.reason is None
    assert shown.size_bytes == _on_disk(tmp_path)
