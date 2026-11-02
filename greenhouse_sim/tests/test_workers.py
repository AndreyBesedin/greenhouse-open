"""A worker executes an epoch into the run store (P17.7, decision 0065): the
three drivers write the same epoch, a reader sees what is committed while the
epoch goes on, and an epoch that stops, ends early or fails says so."""

import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import playback
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.run_store import EpochManifest, EpochStore, FolderStore, Status
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.sensors import delivered_between
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.stored_playback import StoredEpoch
from greenhouse_sim.services.workers import Free, Paced, Stepped, execute, queued

BOX: Final = "climate_box"
SHORT: Final = "climate_box_short"
DAYS: Final = 2
WAIT_S: Final = 180.0


@pytest.fixture
def simulator() -> Iterator[Simulator]:
    """A simulator with the climate box cut to a run of two days."""
    with Simulator() as made:
        config = SCENARIO_REGISTRY[BOX].model_copy(
            update=dict(greenhouse_id=SHORT, duration_days=DAYS)
        )
        made.catalogue.register(config)
        yield made


def _queued(simulator: Simulator, tmp_path: Path, seed: int | None = None) -> EpochStore:
    return queued(simulator, FolderStore(tmp_path), SHORT, seed=seed)


def _trajectory(epoch: EpochStore) -> tuple[object, ...]:
    """What an epoch holds, apart from where it is: its spans, its records, its
    last checkpoint. (A commit's digest names its objects by path, which holds
    the epoch's number, so two epochs of one run never share one.)"""
    return (
        [(c.start_s, c.end_s, c.counts) for c in epoch.commits()],
        [o.model_dump_json() for o in epoch.observations().records],
        [e.model_dump_json() for e in epoch.events().records],
        epoch.checkpoint_at(epoch.frontier_s()),
    )


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


def test_an_epoch_is_queued_in_the_store_before_it_is_executed(
    simulator: Simulator, tmp_path: Path
) -> None:
    first = _queued(simulator, tmp_path)
    again = _queued(simulator, tmp_path)
    other = _queued(simulator, tmp_path, seed=7)

    assert first.manifest().status == Status.QUEUED
    assert first.manifest().duration_s == DAYS * DAY_S
    assert (first.epoch, again.epoch) == (0, 1) and again.run_id == first.run_id
    assert other.run_id != first.run_id and other.manifest().seed == 7
    assert first.commits() == []


def test_a_free_epoch_is_worked_out_to_its_end_a_day_at_a_time(
    simulator: Simulator, tmp_path: Path
) -> None:
    epoch = _queued(simulator, tmp_path)

    status = execute(simulator, epoch, Free())

    assert status == Status.FINISHED == epoch.manifest().status
    assert [(c.start_s, c.end_s) for c in epoch.commits()] == [
        (0.0, DAY_S),
        (DAY_S, 2 * DAY_S),
    ]
    assert all(c.checkpoint for c in epoch.commits())
    epoch.verify()


def test_the_three_drivers_write_the_same_epoch(simulator: Simulator, tmp_path: Path) -> None:
    free = _queued(simulator, tmp_path)
    paced = _queued(simulator, tmp_path)
    stepped = _queued(simulator, tmp_path)
    hourly = [hour * 3600.0 for hour in range(1, 24 * DAYS + 1)]

    assert execute(simulator, free, Free()) == Status.FINISHED
    assert execute(simulator, paced, Paced(seconds_per_day=1.0)) == Status.FINISHED
    assert execute(simulator, stepped, Stepped(hourly)) == Status.FINISHED

    assert _trajectory(free) == _trajectory(paced) == _trajectory(stepped)


def test_an_epoch_is_read_as_far_as_it_is_committed_while_it_goes_on(
    simulator: Simulator, tmp_path: Path
) -> None:
    """The store's commit is all that a reader and the worker share."""
    epoch = _queued(simulator, tmp_path)
    first_day_kept, go_on = threading.Event(), threading.Event()

    def barriers() -> Iterator[float]:
        yield DAY_S
        first_day_kept.set()
        assert go_on.wait(WAIT_S)
        yield 2 * DAY_S

    worker = threading.Thread(target=execute, args=(simulator, epoch, Stepped(barriers())))
    worker.start()
    try:
        assert first_day_kept.wait(WAIT_S)
        reading = StoredEpoch(simulator, epoch.objects, epoch.run_id, epoch.epoch)
        assert reading.status() == Status.RUNNING
        assert reading.frontier_s() == DAY_S
        kept = reading.observations(0, 10**6, DAY_S)
        assert kept.records
    finally:
        go_on.set()
        worker.join(WAIT_S)
    assert epoch.manifest().status == Status.FINISHED
    again = StoredEpoch(simulator, epoch.objects, epoch.run_id, epoch.epoch)
    # What was read before is what is read after: records extend, never change.
    assert again.observations(0, 10**6, DAY_S).records == kept.records


def test_an_epoch_told_to_stop_ends_interrupted_at_the_day_it_reached(
    simulator: Simulator, tmp_path: Path
) -> None:
    epoch = _queued(simulator, tmp_path)
    stopping = threading.Event()

    def barriers() -> Iterator[float]:
        yield DAY_S
        stopping.set()
        yield 2 * DAY_S

    assert execute(simulator, epoch, Stepped(barriers()), stop=stopping) == Status.INTERRUPTED
    assert epoch.manifest().status == Status.INTERRUPTED
    assert epoch.frontier_s() == DAY_S


def test_barriers_that_end_before_the_run_leave_the_epoch_interrupted(
    simulator: Simulator, tmp_path: Path
) -> None:
    epoch = _queued(simulator, tmp_path)

    assert execute(simulator, epoch, Stepped([DAY_S])) == Status.INTERRUPTED
    assert epoch.frontier_s() == DAY_S


def test_an_epoch_whose_simulation_fails_ends_failed(
    simulator: Simulator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    epoch = _queued(simulator, tmp_path)
    worked = delivered_between

    def failing_on_the_second_day(
        simulator: Simulator, run: RunRequest, *args: Any, **kw: Any
    ) -> Any:
        if args and args[0] == DAY_S:
            raise RuntimeError("a simulation that fails")
        return worked(simulator, run, *args, **kw)

    monkeypatch.setattr(playback, "delivered_between", failing_on_the_second_day)

    assert execute(simulator, epoch, Free()) == Status.FAILED
    assert epoch.frontier_s() == DAY_S


def test_an_epoch_that_has_begun_is_not_executed_again(
    simulator: Simulator, tmp_path: Path
) -> None:
    epoch = _queued(simulator, tmp_path)
    execute(simulator, epoch, Stepped([DAY_S]))

    with pytest.raises(Conflict):
        execute(simulator, epoch, Free())


def test_an_epoch_of_another_run_than_its_manifest_names_is_refused(
    simulator: Simulator, tmp_path: Path
) -> None:
    objects = FolderStore(tmp_path)
    elsewhere = EpochStore.create(
        objects,
        EpochManifest(run_id="not-this-run", epoch=0, scenario_id=SHORT, layout="default"),
    )

    with pytest.raises(ValueError, match="not-this-run"):
        execute(simulator, elsewhere, Free())
    assert elsewhere.manifest().status == Status.QUEUED
