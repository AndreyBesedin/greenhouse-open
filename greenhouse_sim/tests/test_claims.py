"""A claim on an epoch (P18.4, decision 0067): the store's *create unless it exists*
decides who works an epoch, with no lock across processes, however they interleave,
and a claim its holder left behind blocks no one."""

import json
import multiprocessing
import os
import signal
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.services import interrupted, leases, scheduler, workers
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    EpochTaken,
    FolderStore,
    Status,
)
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, execute, queued, resume

# A worker starts from nothing and imports what it is told to run by name.
sys.path.insert(0, str(Path(__file__).parent))

import claims_support
import workers_support

SHORT: Final = workers_support.SHORT
CONTENDERS: Final = 6
ROUNDS: Final = 40
JOIN_S: Final = 120.0
SPAWN: Final = multiprocessing.get_context("spawn")


class _Meanwhile(FolderStore):
    """A store that does `meanwhile` as its first write is about to be made: whoever
    writes through it has done all its reading and stands where a process is stopped.
    Or just after a creation, for one that has claimed and stands there."""

    def __init__(self, root: Path, meanwhile: Callable[[], None], *, after: bool = False) -> None:
        super().__init__(root)
        self._meanwhile: Callable[[], None] | None = meanwhile
        self._after = after

    def _writing(self) -> None:
        if self._meanwhile is not None:
            meanwhile, self._meanwhile = self._meanwhile, None
            meanwhile()

    def put(self, name: str, data: bytes) -> None:
        if not self._after:
            self._writing()
        super().put(name, data)

    def create(self, name: str, data: bytes) -> bool:
        if not self._after:
            self._writing()
        made = super().create(name, data)
        self._writing()
        return made

    def delete(self, name: str) -> None:
        if not self._after:
            self._writing()
        super().delete(name)


def _epoch(objects: FolderStore, *, number: int = 0, status: Status = Status.QUEUED) -> EpochStore:
    return EpochStore.create(
        objects,
        EpochManifest(run_id="run", epoch=number, scenario_id="s", layout="default", status=status),
    )


def _race(target: Callable[..., None], root: Path, rounds: int) -> list[Any]:
    """`CONTENDERS` processes given `target`, each round begun together, and all
    they said."""
    ready, won = SPAWN.Barrier(CONTENDERS), SPAWN.Queue()
    racing = [
        SPAWN.Process(target=target, args=(str(root), rounds, ready, won))
        for _ in range(CONTENDERS)
    ]
    for process in racing:
        process.start()
    for process in racing:
        process.join(JOIN_S)
        assert process.exitcode == 0
    said = []
    while not won.empty():
        said.append(won.get())
    return said


# The store's operation.


def test_an_object_is_created_once_and_then_only_a_deletion_frees_its_name(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)

    assert objects.create("a/b", b"first")
    assert not objects.create("a/b", b"second")
    assert objects.get("a/b") == b"first"

    objects.put("a/b", b"put")
    assert not objects.create("a/b", b"third")
    assert objects.get("a/b") == b"put"

    objects.delete("a/b")
    assert objects.create("a/b", b"fourth")
    assert objects.get("a/b") == b"fourth"
    assert objects.names("a/") == ["a/b"]


def test_a_creation_cut_short_leaves_no_object_and_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    objects = FolderStore(tmp_path)

    def cut_short(_descriptor: int) -> None:
        raise OSError("no room")

    with monkeypatch.context() as cut:
        cut.setattr(os, "fsync", cut_short)
        with pytest.raises(OSError, match="no room"):
            objects.create("a", b"data")
    assert objects.get("a") is None
    assert list(tmp_path.iterdir()) == []

    assert objects.create("a", b"data")
    assert [p.name for p in tmp_path.iterdir()] == ["a"]


def test_of_processes_creating_one_object_exactly_one_makes_it(tmp_path: Path) -> None:
    said = _race(claims_support.creates, tmp_path, ROUNDS)

    objects = FolderStore(tmp_path)
    assert Counter(number for number, _pid in said) == dict.fromkeys(range(ROUNDS), 1)
    for number, pid in said:
        assert objects.get(f"race/{number}") == str(pid).encode()
    assert len(list((tmp_path / "race").iterdir())) == ROUNDS


# Claims, in a forced order.


@pytest.mark.parametrize("meanwhile", ["claimed", "claimed and let go", "claimed again"])
def test_a_process_stopped_before_it_creates_its_claim_is_refused_whatever_came_since(
    tmp_path: Path, meanwhile: str
) -> None:
    plain = FolderStore(tmp_path)
    _epoch(plain)
    others = EpochStore(plain, "run", 0), EpochStore(plain, "run", 0)

    def others_come() -> None:
        assert others[0].claim()
        if meanwhile != "claimed":
            others[0].let_go()
        if meanwhile == "claimed again":
            assert others[1].claim()

    stopped = EpochStore(_Meanwhile(tmp_path, others_come), "run", 0)

    assert not stopped.claim()

    assert not stopped.claimed()
    assert others[0].claimed() == (meanwhile == "claimed")
    assert others[1].claimed() == (meanwhile == "claimed again")
    for other in others:
        other.let_go()


@pytest.mark.parametrize("starts", [resume, execute], ids=["resume", "execute"])
def test_a_worker_stopped_before_its_first_write_finds_the_epoch_taken(
    tmp_path: Path, starts: Callable[..., Status]
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        kept = queued(made, objects, SHORT)
    ended = []

    def another_works_it_out() -> None:
        with workers_support.short_simulator() as another:
            ended.append(resume(another, EpochStore(objects, kept.run_id, kept.epoch), Free()))

    stopped = EpochStore(_Meanwhile(tmp_path, another_works_it_out), kept.run_id, kept.epoch)

    with workers_support.short_simulator() as made, pytest.raises(Conflict):
        starts(made, stopped, Free())

    assert ended == [Status.FINISHED]
    assert kept.manifest().status == Status.FINISHED
    assert len(kept.commits()) == workers_support.SHORT_DAYS
    kept.verify()


def test_an_epoch_taken_up_as_it_is_about_to_be_told_interrupted_is_not_told(
    tmp_path: Path,
) -> None:
    """Told by a server that found no one working it, stopped just before its write."""
    plain = FolderStore(tmp_path)
    _epoch(plain)
    worker = EpochStore(plain, "run", 0)

    def taken_up() -> None:
        worker.set_status(Status.RUNNING)

    with Simulator() as simulator:
        simulator.runs = _Meanwhile(tmp_path, taken_up)

        assert interrupted.mark(simulator) == []

    assert worker.manifest().status == Status.RUNNING
    assert worker.claimed() and worker.worked()
    worker.set_status(Status.FINISHED)


def test_a_worker_coming_as_an_epoch_is_told_interrupted_leaves_it_interrupted(
    tmp_path: Path,
) -> None:
    plain = FolderStore(tmp_path)
    _epoch(plain)
    worker = EpochStore(plain, "run", 0)
    refused = []

    def comes_too_late() -> None:
        refused.append(worker.claim())

    with Simulator() as simulator:
        simulator.runs = _Meanwhile(tmp_path, comes_too_late, after=True)

        (told,) = interrupted.mark(simulator)

    assert refused == [False]
    assert told.status == Status.INTERRUPTED
    assert not worker.worked()


def test_a_process_that_says_an_epoch_runs_with_another_holding_it_is_refused(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    holder = _epoch(objects)
    assert holder.claim()

    with pytest.raises(EpochTaken):
        EpochStore(objects, "run", 0).set_status(Status.RUNNING)

    holder.set_status(Status.RUNNING)
    assert holder.claimed()
    holder.set_status(Status.FINISHED)


def test_what_a_crash_left_past_the_last_commit_is_removed_and_the_claim_is_not(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    epoch = _epoch(objects)
    assert epoch.claim()
    objects.put("run/0/segments/left/observations.parquet", b"half")

    assert epoch.discard_uncommitted() == ["run/0/segments/left/observations.parquet"]

    assert epoch.claimed()
    epoch.let_go()


def test_a_worker_refused_changes_nothing_in_the_store(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    ended = _epoch(objects, status=Status.FINISHED)
    before = objects.names()

    with Simulator() as simulator, pytest.raises(Conflict):
        resume(simulator, ended, Free())

    assert objects.names() == before


def test_a_worker_that_fails_as_it_begins_lets_go_of_the_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def cannot_begin(*_args: object) -> Status:
        raise OSError("no room")

    monkeypatch.setattr(workers, "_drive", cannot_begin)
    objects = FolderStore(tmp_path)
    epoch = _epoch(objects)

    with Simulator() as simulator, pytest.raises(OSError, match="no room"):
        resume(simulator, epoch, Free())

    assert not epoch.worked()
    assert epoch.manifest().status == Status.QUEUED


# Claims, in processes of their own.


def test_of_processes_claiming_one_epoch_exactly_one_takes_it(tmp_path: Path) -> None:
    """Half the epochs have a claim left that has expired: one takes each of them too."""
    objects = FolderStore(tmp_path)
    for number in range(ROUNDS):
        _epoch(objects, number=number)
        if number % 2:
            left = json.dumps({"refreshed_at": time.time() - 2 * leases.EXPIRES_AFTER_S})
            assert objects.create(f"run/{number}/{leases.CLAIMS}/00000000.json", left.encode())

    said = _race(claims_support.claims, tmp_path, ROUNDS)

    assert Counter(said) == dict.fromkeys(range(ROUNDS), 1)
    for number in range(ROUNDS):
        # Each took the one number after what it read.
        assert leases.newest(objects, f"run/{number}") == number % 2


def test_of_two_workers_given_one_epoch_one_works_it_and_the_other_leaves(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        kept = queued(made, objects, SHORT)
        whole = queued(made, FolderStore(tmp_path / "whole"), SHORT)
        assert execute(made, whole, Free()) == Status.FINISHED
    both = [
        SPAWN.Process(target=scheduler.work, args=(str(tmp_path), kept.run_id, kept.epoch))
        for _ in range(2)
    ]

    for process in both:
        process.start()
    for process in both:
        process.join(JOIN_S)

    assert sorted(process.exitcode or 0 for process in both) == [0, scheduler.LEFT_TO_ANOTHER]
    assert kept.manifest().status == Status.FINISHED
    assert [c.digest for c in kept.commits()] == [c.digest for c in whole.commits()]
    kept.verify()


def test_a_worker_given_an_epoch_that_no_longer_waits_leaves_it_as_it_is(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    told = _epoch(objects, status=Status.INTERRUPTED)

    with pytest.raises(SystemExit) as left:
        scheduler.work(str(tmp_path), "run", 0)

    assert left.value.code == scheduler.LEFT_TO_ANOTHER
    assert told.manifest().status == Status.INTERRUPTED
    assert not told.worked()


def test_a_worker_that_leaves_an_epoch_to_another_has_nothing_said_of_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler, "work", claims_support.leaves_to_another)
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        made.runs = objects
        made.scheduler = scheduler.Scheduler(made, tmp_path, limit=1)
        shown = made.scheduler.start(SHORT)
        deadline = time.monotonic() + JOIN_S
        while made.scheduler.workers():
            assert time.monotonic() < deadline, "waited for the worker to leave"
            time.sleep(0.02)

        assert EpochStore(objects, shown.run_id, shown.epoch).manifest().status == Status.QUEUED


# A claim whose holder is gone.


def test_a_worker_killed_with_the_epoch_claimed_blocks_it_only_until_the_claim_expires(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        kept = queued(made, objects, SHORT)
        whole = queued(made, FolderStore(tmp_path / "whole"), SHORT)
        assert execute(made, whole, Free()) == Status.FINISHED
    killed = SPAWN.Process(
        target=claims_support.claims_and_is_killed, args=(str(tmp_path), kept.run_id, kept.epoch)
    )
    killed.start()
    killed.join(JOIN_S)
    assert killed.exitcode == -signal.SIGKILL

    assert kept.worked()
    assert not EpochStore(objects, kept.run_id, kept.epoch).claim()
    with workers_support.short_simulator() as made, pytest.raises(Conflict, match="worked by"):
        resume(made, kept, Free())

    assert not kept.worked(now=time.time() + leases.EXPIRES_AFTER_S + 1)
    # Its time taken as passed, for a worker that takes the time from the clock.
    old = json.dumps({"refreshed_at": time.time() - 2 * leases.EXPIRES_AFTER_S})
    objects.put(f"{kept.run_id}/{kept.epoch}/{leases.CLAIMS}/00000000.json", old.encode())

    with workers_support.short_simulator() as made:
        assert resume(made, kept, Free()) == Status.FINISHED

    assert [c.digest for c in kept.commits()] == [c.digest for c in whole.commits()]
    assert not kept.worked()


def test_of_two_who_read_one_expired_claim_one_takes_the_epoch(tmp_path: Path) -> None:
    plain = FolderStore(tmp_path)
    _epoch(plain)
    assert leases.claim(plain, "run/0") == 0
    later = time.time() + leases.EXPIRES_AFTER_S + 1
    other = EpochStore(plain, "run", 0)

    def other_comes() -> None:
        assert other.claim(now=later)

    stopped = EpochStore(_Meanwhile(tmp_path, other_comes), "run", 0)

    assert not stopped.claim(now=later)

    assert other.claimed()
    other.let_go()


def test_an_epoch_no_one_holds_any_more_is_told_interrupted_and_then_can_be_claimed(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    left = _epoch(objects, status=Status.RUNNING)
    assert leases.claim(objects, "run/0") == 0
    later = time.time() + leases.EXPIRES_AFTER_S + 1

    with Simulator() as simulator:
        simulator.runs = objects
        assert interrupted.mark(simulator) == []
        (told,) = interrupted.mark(simulator, now=later)

    assert told.status == Status.INTERRUPTED
    assert not left.worked()
    assert left.claim()
    left.let_go()
