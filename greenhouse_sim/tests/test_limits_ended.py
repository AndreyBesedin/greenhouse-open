"""An epoch ended by a limit (P18.3, decision 0067): by the bytes it keeps, its worker's
memory or its time, by a real worker, with the limit and the figures as its reason. It
keeps what it committed, and carried on or forked it gives the digests of a run never
ended, none of which the limits touch."""

import logging
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import scheduler
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.limits import Budget, LimitPassed, Limits
from greenhouse_sim.services.resources import ProcessUse, machine_memory_bytes
from greenhouse_sim.services.run_store import (
    EpochStore,
    EpochUsage,
    FolderStore,
    Status,
    stored_run,
)
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Stepped, execute, queued

sys.path.insert(0, str(Path(__file__).parent))

import workers_support

SHORT: Final = workers_support.SHORT
SEED: Final = 3
WAIT_S: Final = 60.0
UNLIMITED: Final = Limits(worker_memory_bytes=None)
FIELD_NAMES: Final = tuple(Limits.model_fields)
MEBIBYTE: Final = 1024**2
# Each passed by any worker at its first look, as it takes the epoch up.
AT_ONCE: Final = {
    "memory": Limits(worker_memory_bytes=1),
    "cpu": Limits(epoch_cpu_s=0.001),
    "wall": Limits(epoch_wall_s=0.001),
}
SAYS: Final = {
    "memory": ("held", "of memory", "1 B"),
    "cpu": ("of a core", "0.00 s"),
    "wall": ("from its worker's start", "0.00 s"),
}


def _until(holds: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not holds():
        if time.monotonic() > deadline:
            raise AssertionError(f"waited {WAIT_S} s for {what}")
        time.sleep(0.02)


def _digests(epoch: EpochStore) -> list[str]:
    return [commit.digest for commit in epoch.commits()]


def _ended(simulator: Simulator, epoch: EpochStore) -> None:
    """Until the epoch has ended and its worker is gone."""
    _until(lambda: epoch.manifest().status in (Status.FINISHED, Status.FAILED), "it to end")
    _until(lambda: scheduler.of(simulator).workers() == [], "its worker to go")


def _simulator(store: Path, limits: Limits) -> Simulator:
    made = workers_support.short_simulator()
    made.runs = FolderStore(store)
    made.limits = limits
    return made


def _run(store: Path, limits: Limits) -> EpochStore:
    """A run of the short scenario, computed by a worker to its end, whichever it is."""
    with _simulator(store, limits) as simulator:
        shown = scheduler.start(simulator, SHORT, seed=SEED)
        epoch = EpochStore(FolderStore(store), shown.run_id, shown.epoch)
        _ended(simulator, epoch)
    return epoch


@pytest.fixture(scope="module")
def never_ended(tmp_path_factory: pytest.TempPathFactory) -> Iterator[EpochStore]:
    """The run no limit ended, as a worker computes it: what the others come to."""
    yield _run(tmp_path_factory.mktemp("never"), UNLIMITED)


def _in_words(reason: str | None, *figures: str) -> None:
    assert reason is not None
    assert "raised" in reason, reason
    assert all(figure in reason for figure in figures), reason
    assert not any(name in reason for name in FIELD_NAMES), reason


def test_the_defaults_say_nothing_of_bytes_or_time_and_share_half_the_machine() -> None:
    assert Limits().epoch_bytes is None
    assert Limits().epoch_cpu_s is None and Limits().epoch_wall_s is None
    assert Limits().worker_memory_bytes == machine_memory_bytes() // 2 // 2
    assert Limits(workers=4).worker_memory_bytes == machine_memory_bytes() // 2 // 4
    assert Limits(worker_memory_bytes=None).budget == Budget()


def test_a_budget_changes_no_digest_and_a_scheduler_gives_each_run_one(
    never_ended: EpochStore, tmp_path: Path
) -> None:
    limits = Limits(epoch_bytes=10**12, epoch_cpu_s=10**6, epoch_wall_s=10**6)

    limited = _run(tmp_path, limits)

    assert limited.manifest().status == Status.FINISHED
    assert limited.run_id == never_ended.run_id
    assert _digests(limited) == _digests(never_ended)
    assert limited.budget() == limits.budget
    assert never_ended.budget() == UNLIMITED.budget


def test_an_epoch_past_its_bytes_ends_at_that_commit_which_stands(
    never_ended: EpochStore, tmp_path: Path
) -> None:
    ended = _run(tmp_path, Limits(epoch_bytes=1))

    manifest = ended.manifest()
    assert manifest.status == Status.FAILED and manifest.past_limit
    _in_words(manifest.reason, "it kept", "what one run may keep", "1 B")
    # What it committed is the run's, and can be read and checked.
    assert _digests(ended) == _digests(never_ended)[:1]
    ended.verify()
    assert ended.observations().records
    usage = ended.usage()
    assert usage is not None and usage.commits == 1 and usage.frontier_s == DAY_S
    with _simulator(tmp_path, UNLIMITED) as simulator:
        answered = respond(simulator, "GET", f"/api/runs/{ended.run_id}/epochs/{ended.epoch}")
    assert answered.status == HTTPStatus.OK
    assert isinstance(answered.body, dict) and answered.body["reason"] == manifest.reason
    # Which a client reads to offer to carry it on, as one interrupted is.
    assert answered.body["past_limit"] is True


def test_an_epoch_at_a_pace_past_its_bytes_ends_at_that_commit_too(tmp_path: Path) -> None:
    with _simulator(tmp_path, Limits(epoch_bytes=1)) as simulator:
        shown = scheduler.start(simulator, SHORT, seed=SEED, seconds_per_day=0.2)
        epoch = EpochStore(FolderStore(tmp_path), shown.run_id, shown.epoch)
        _ended(simulator, epoch)

    assert epoch.manifest().status == Status.FAILED and epoch.manifest().past_limit
    assert len(epoch.commits()) == 1


def test_its_last_commit_past_its_bytes_ends_nothing_since_it_has_finished(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        epoch = queued(made, objects, SHORT)
    epoch.keep_to(Budget(epoch_bytes=1))

    with pytest.raises(LimitPassed):
        epoch.commit(0.0, DAY_S)
    assert epoch.manifest().status == Status.FAILED

    last = queued(made, objects, SHORT, seed=1)
    last.keep_to(Budget(epoch_bytes=1))
    duration = last.manifest().duration_s
    assert duration is not None
    last.commit(0.0, duration)
    assert last.manifest().status == Status.QUEUED


def test_it_is_refused_a_resume_while_the_limit_stands_then_ends_as_a_run_never_ended(
    never_ended: EpochStore, tmp_path: Path
) -> None:
    limits = Limits(epoch_bytes=1)
    ended = _run(tmp_path, limits)
    before = ended.manifest()

    with _simulator(tmp_path, limits) as simulator, pytest.raises(Conflict) as refused:
        scheduler.resume(simulator, ended.run_id, ended.epoch)
    _in_words(refused.value.message, "it kept", "1 B")
    assert ended.manifest() == before

    with _simulator(tmp_path, UNLIMITED) as simulator:
        shown = scheduler.resume(simulator, ended.run_id, ended.epoch)
        assert shown.status in (Status.QUEUED, Status.RUNNING) and shown.reason is None
        assert not ended.manifest().past_limit
        _ended(simulator, ended)

    after = ended.manifest()
    assert after.status == Status.FINISHED and after.reason is None
    assert ended.budget() == UNLIMITED.budget
    assert (shown.run_id, shown.epoch) == (ended.run_id, ended.epoch)
    assert _digests(ended) == _digests(never_ended)


def test_a_resume_refused_for_a_limit_writes_nothing_of_what_an_older_epoch_lacks(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as first:
        first.runs = objects
        kept = workers_support.with_one_day_committed(first, objects)
    workers_support.as_from_before_it_carried_a_file(objects, kept)
    written = sorted(path for path in tmp_path.rglob("*") if path.is_file())
    manifest = kept.manifest()

    with (
        _simulator(tmp_path, Limits(epoch_bytes=1)) as simulator,
        pytest.raises(Conflict) as refused,
    ):
        scheduler.resume(simulator, kept.run_id, kept.epoch)

    _in_words(refused.value.message, "it kept", "1 B")
    assert sorted(path for path in tmp_path.rglob("*") if path.is_file()) == written
    assert kept.manifest() == manifest


def test_a_budget_that_cannot_be_read_stops_no_server_and_is_written_again(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as first:
        waiting = queued(first, objects, SHORT, queued_at=datetime.now(UTC))
    objects.put(f"{waiting.run_id}/{waiting.epoch}/budget.json", b"not a budget")
    assert waiting.budget() is None

    limits = Limits(workers=1, waiting_runs=1)
    with Simulator(runs=objects, limits=limits) as second:
        scheduler.of(second)
        assert waiting.budget() == limits.budget


def test_a_fork_of_it_is_the_fork_of_a_run_never_ended(
    never_ended: EpochStore, tmp_path: Path
) -> None:
    ended = _run(tmp_path, Limits(epoch_bytes=1))
    with _simulator(tmp_path, UNLIMITED) as simulator:
        fork = scheduler.fork(simulator, ended.run_id, ended.epoch, DAY_S)
        forked = EpochStore(FolderStore(tmp_path), fork.run_id, fork.epoch)
        _ended(simulator, forked)

    assert forked.manifest().status == Status.FINISHED
    assert forked.budget() == UNLIMITED.budget
    root = never_ended.objects
    assert isinstance(root, FolderStore)
    with _simulator(root.root, UNLIMITED) as simulator:
        made = scheduler.fork(simulator, never_ended.run_id, never_ended.epoch, DAY_S)
        other = EpochStore(root, made.run_id, made.epoch)
        _ended(simulator, other)
    assert _digests(forked) == _digests(other)
    assert forked.run_id == other.run_id


@pytest.mark.parametrize("limit", AT_ONCE)
def test_a_real_worker_past_its_memory_or_time_ends_saying_which_and_carries_on_to_the_same_digests(
    never_ended: EpochStore, tmp_path: Path, limit: str
) -> None:
    ended = _run(tmp_path, AT_ONCE[limit])

    manifest = ended.manifest()
    assert manifest.status == Status.FAILED and manifest.past_limit
    _in_words(manifest.reason, *SAYS[limit])
    assert not ended.worked()
    kept = _digests(ended)
    assert kept == _digests(never_ended)[: len(kept)]

    with _simulator(tmp_path, UNLIMITED) as simulator:
        scheduler.resume(simulator, ended.run_id, ended.epoch)
        _ended(simulator, ended)

    assert ended.manifest().status == Status.FINISHED
    assert _digests(ended) == _digests(never_ended)


def test_a_workers_time_is_added_to_its_epochs_and_its_memory_is_its_own(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        epoch = queued(made, objects, SHORT)
    objects.put(
        f"{epoch.run_id}/{epoch.epoch}/usage.json",
        EpochUsage(
            commits=0,
            checkpoints=0,
            frontier_s=0.0,
            days_computed=0.0,
            bytes_kept=0,
            cpu_s=5.0,
            peak_memory_bytes=900,
            wall_s=7.0,
        )
        .model_dump_json()
        .encode(),
    )

    epoch.counted_by(lambda: ProcessUse(1.0, 10, 2.0))

    assert epoch.used_so_far() == ProcessUse(6.0, 10, 9.0)
    written = epoch.write_usage([])
    assert written.cpu_s == 6.0 and written.wall_s == 9.0 and written.peak_memory_bytes == 900


def test_an_end_by_a_limit_is_not_logged_as_a_failure_of_the_store(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with workers_support.short_simulator() as made:
        epoch = queued(made, FolderStore(tmp_path), SHORT)
        epoch.keep_to(Budget(epoch_bytes=1))
        with caplog.at_level(logging.WARNING):
            assert execute(made, epoch, Stepped([DAY_S, 2 * DAY_S])) == Status.FAILED

    assert len(epoch.commits()) == 1 and epoch.manifest().past_limit
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


def test_time_counts_across_a_resume_and_a_worker_memory_does_not(tmp_path: Path) -> None:
    ended = _run(tmp_path, AT_ONCE["cpu"])
    used = ended.usage()
    assert used is not None and used.cpu_s and used.wall_s and used.peak_memory_bytes

    with _simulator(tmp_path, AT_ONCE["cpu"]) as simulator, pytest.raises(Conflict) as refused:
        scheduler.resume(simulator, ended.run_id, ended.epoch)
    _in_words(refused.value.message, "of a core")

    # Memory is each worker's own: the request is let in, and its worker ends it.
    with _simulator(tmp_path, Limits(worker_memory_bytes=1)) as simulator:
        scheduler.resume(simulator, ended.run_id, ended.epoch)
        _ended(simulator, ended)
    assert ended.manifest().past_limit
    _in_words(ended.manifest().reason, "of memory")


@pytest.mark.parametrize(
    ("budget", "target", "says"),
    [
        (Budget(worker_memory_bytes=300 * MEBIBYTE), "takes_memory", "of memory"),
        (Budget(epoch_wall_s=1.0), "holds_a_day", "from its worker's start"),
        (Budget(epoch_cpu_s=1.0), "spins_a_day", "of a core"),
    ],
    ids=["memory", "wall", "cpu"],
)
def test_a_worker_is_ended_where_it_stands_between_commits_keeping_what_it_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    budget: Budget,
    target: str,
    says: str,
) -> None:
    monkeypatch.setattr(scheduler, "work", getattr(workers_support, target))
    limits = Limits(
        worker_memory_bytes=budget.worker_memory_bytes,
        epoch_cpu_s=budget.epoch_cpu_s,
        epoch_wall_s=budget.epoch_wall_s,
    )

    ended = _run(tmp_path, limits)

    manifest = ended.manifest()
    assert manifest.status == Status.FAILED and manifest.past_limit
    _in_words(manifest.reason, says)
    assert [commit.end_s for commit in ended.commits()] == [DAY_S]
    assert not ended.worked()
    objects = ended.objects
    assert stored_run(objects, ended.run_id, ended.epoch).reason == manifest.reason


def test_what_a_limit_said_of_an_epoch_is_the_last_word_of_its_process_and_comes_second(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        epoch = queued(made, objects, SHORT)
        other = queued(made, objects, SHORT, seed=1)

    assert epoch.end_past_limit("past a limit")
    epoch.set_status(Status.RUNNING)
    assert epoch.manifest().status == Status.FAILED
    assert epoch.manifest().reason == "past a limit"

    # One that has finished is not told otherwise.
    other.set_status(Status.FINISHED)
    assert not other.end_past_limit("past a limit")
    assert other.manifest().status == Status.FINISHED


def test_while_a_process_is_being_ended_its_working_thread_cannot_take_the_epoch_again(
    tmp_path: Path,
) -> None:
    with workers_support.short_simulator() as made:
        epoch = queued(made, FolderStore(tmp_path), SHORT)
    said = threading.Thread(target=epoch.claim, daemon=True)

    with epoch.saying:
        said.start()
        said.join(0.2)
        # Whatever the machine's load, it has not got past the lock this thread holds.
        assert said.is_alive() and not epoch.claimed()

    said.join(WAIT_S)
    assert epoch.claimed()
    epoch.let_go()


def test_a_failure_of_any_other_kind_is_still_not_carried_on(tmp_path: Path) -> None:
    with _simulator(tmp_path, UNLIMITED) as simulator:
        epoch = queued(simulator, FolderStore(tmp_path), SHORT)
        epoch.set_status(Status.FAILED, reason="something else")

        with pytest.raises(Conflict, match="only an interrupted one resumes"):
            scheduler.resume(simulator, epoch.run_id, epoch.epoch)


def test_a_run_that_waits_through_a_restart_takes_the_limits_of_the_server_after_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler, "work", workers_support.holds_its_place)
    objects = FolderStore(tmp_path)
    with _simulator(tmp_path, Limits(workers=1, epoch_bytes=1)) as first:
        scheduler.start(first, SHORT, seed=1)
        scheduler.start(first, SHORT, seed=2)
        waiting = scheduler.start(first, SHORT, seed=3)
    epoch = EpochStore(objects, waiting.run_id, waiting.epoch)
    assert epoch.budget() == Limits(workers=1, epoch_bytes=1).budget

    raised = Limits(workers=1, epoch_bytes=10)
    claims = objects.names(f"{epoch.run_id}/{epoch.epoch}/leases/")
    with Simulator(runs=objects, limits=raised) as second:
        assert (epoch.run_id, epoch.epoch) in scheduler.of(second).waiting()
        assert epoch.budget() == raised.budget
        assert epoch.manifest().status == Status.QUEUED
        # Given without claiming the epoch, or writing over what a worker says of it.
        assert objects.names(f"{epoch.run_id}/{epoch.epoch}/leases/") == claims


def test_what_a_crash_left_past_a_commit_takes_nothing_of_the_budget(tmp_path: Path) -> None:
    with workers_support.short_simulator() as made:
        epoch = queued(made, FolderStore(tmp_path), SHORT)
    epoch.give_budget(Budget(epoch_bytes=5))

    assert epoch.discard_uncommitted() == []
    assert epoch.budget() == Budget(epoch_bytes=5)
