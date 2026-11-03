"""A played run kept in the run store (P17.3, decision 0065): each day the
clock has passed written as a segment of its records with a checkpoint,
the epoch's status told, its epochs counted by the store, and the run
asked for at a seed."""

import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import playback
from greenhouse_sim.services.checkpoints import load_openings
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    Status,
    StoredRun,
    delete_epoch,
    stored_runs,
)
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import layout_name
from greenhouse_sim.services.sensors import delivered_between
from greenhouse_sim.services.simulator import Simulator

BOX: Final = "climate_box"
REFERENCE: Final = "reference_greenhouse"
SHORT: Final = "reference_greenhouse_short"
EVERY_S: Final = 300.0
ALL: Final = 10**6
WAIT_S: Final = 180.0


class Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


@pytest.fixture
def short() -> Iterator[Simulator]:
    """A simulator with the reference greenhouse cut to a run of two days."""
    with Simulator() as made:
        load_openings(made)
        config = SCENARIO_REGISTRY[REFERENCE].model_copy(
            update=dict(greenhouse_id=SHORT, duration_days=2)
        )
        made.catalogue.register(config)
        yield made


def _kept(epochs: Epochs) -> StoredRun:
    (found,) = stored_runs(epochs.objects, SHORT)
    return found


@pytest.fixture
def played(short: Simulator) -> Iterator[Callable[[Epochs, Clock], Playback]]:
    """Begins the short run, and stops each run begun after the test, so that no
    worker outlives it."""
    begun: list[Playback] = []

    def begin(epochs: Epochs, clock: Clock) -> Playback:
        run = Playback(
            short, SHORT, seconds_per_day=10.0, every_s=EVERY_S, clock=clock, epochs=epochs
        )
        run.begin()
        begun.append(run)
        return run

    yield begin
    for run in begun:
        run.stop()


@pytest.mark.slow
def test_a_run_played_to_its_end_is_kept_as_the_consumer_read_it(
    played: Callable[[Epochs, Clock], Playback], tmp_path: Path
) -> None:
    epochs, clock = Epochs(tmp_path), Clock()
    run = played(epochs, clock)
    assert run.wait_for(2, timeout_s=WAIT_S)
    run.set_targets({"heating_day": 24.0})
    assert run.wait_for(2, timeout_s=WAIT_S)
    # Worked out, but the clock has passed no day: none is kept yet.
    assert (_kept(epochs).status, _kept(epochs).frontier_s) == (Status.RUNNING, 0.0)

    run.command(PlaybackCommand.PLAY)
    clock.now += 10.0
    _until(lambda: _kept(epochs).frontier_s == DAY_S, "the first day to be kept")
    assert _kept(epochs).status == Status.RUNNING and _kept(epochs).progress == 0.5
    clock.now += 10.0
    _until(lambda: _kept(epochs).status == Status.FINISHED, "the run to be kept whole")

    kept = _kept(epochs)
    store = EpochStore(epochs.objects, run.run_id, kept.epoch)
    assert (kept.frontier_s, kept.progress, kept.seed) == (2 * DAY_S, 1.0, None)
    store.verify()
    assert store.observations(0, ALL).records == list(run.records_after(0, ALL).records)
    assert store.events(0, ALL).records == list(run.events_after(0, ALL).records)
    outcomes = run.outcomes_after(0, ALL)[0].outcomes
    assert outcomes and store.outcomes(0, ALL).records == list(outcomes)
    # Positions across the days are the in-memory log's.
    for position in (0, 1, 700, 1_000, 1_449):
        ours, theirs = store.observations(position, 50), run.records_after(position, 50)
        assert (ours.records, ours.next, ours.has_more) == (
            list(theirs.records),
            theirs.next,
            theirs.has_more,
        )
    for day in (1, 2):
        assert store.checkpoint_at(day * DAY_S) is not None
    # A producer started again finds it, and counts on from its epoch.
    again = Epochs(tmp_path)
    assert [(r.run_id, r.epoch, r.status) for r in stored_runs(again.objects)] == [
        (run.run_id, 0, Status.FINISHED)
    ]
    assert again.next(run.run_id) == 1


@pytest.mark.slow
def test_a_restart_and_a_stop_tell_the_epoch_it_was_interrupted(
    played: Callable[[Epochs, Clock], Playback], tmp_path: Path
) -> None:
    epochs, clock = Epochs(tmp_path), Clock()
    run = played(epochs, clock)
    assert run.wait_for(1, timeout_s=WAIT_S)

    run.command(PlaybackCommand.RESTART)
    by_epoch = {r.epoch: r.status for r in stored_runs(epochs.objects, SHORT)}
    assert by_epoch == {0: Status.INTERRUPTED, 1: Status.RUNNING}

    run.stop()
    by_epoch = {r.epoch: r.status for r in stored_runs(epochs.objects, SHORT)}
    assert by_epoch == {0: Status.INTERRUPTED, 1: Status.INTERRUPTED}


@pytest.mark.slow
def test_a_restart_while_the_last_day_is_kept_leaves_the_new_epoch_running(
    played: Callable[[Epochs, Clock], Playback], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old epoch's last day is committed outside the lock: a restart
    meanwhile says it was interrupted and opens the next, which the old
    one's end does not end, and which goes on keeping its own days."""
    epochs, clock = Epochs(tmp_path), Clock()
    committing, restarted = threading.Event(), threading.Event()
    commit = EpochStore.commit

    def held_at_the_last_day(store: EpochStore, start_s: float, *args: Any, **kept: Any) -> Any:
        if store.epoch == 0 and start_s == DAY_S:
            committing.set()
            assert restarted.wait(WAIT_S)
        return commit(store, start_s, *args, **kept)

    monkeypatch.setattr(EpochStore, "commit", held_at_the_last_day)
    run = played(epochs, clock)
    assert run.wait_for(2, timeout_s=WAIT_S)
    run.command(PlaybackCommand.PLAY)
    clock.now += 20.0
    assert committing.wait(WAIT_S)

    run.command(PlaybackCommand.RESTART)
    restarted.set()
    assert run.wait_for(1, timeout_s=WAIT_S)
    run.command(PlaybackCommand.PLAY)
    clock.now += 10.0

    def new_epoch() -> StoredRun:
        return next(r for r in stored_runs(epochs.objects, SHORT) if r.epoch == 1)

    _until(lambda: new_epoch().frontier_s == DAY_S, "the new epoch's first day to be kept")
    by_epoch = {r.epoch: r.status for r in stored_runs(epochs.objects, SHORT)}
    assert by_epoch == {0: Status.INTERRUPTED, 1: Status.RUNNING}


@pytest.mark.slow
def test_a_run_whose_simulation_fails_is_kept_as_failed(
    played: Callable[[Epochs, Clock], Playback], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its worker stops on the failure, which its epoch says, rather than
    that it was interrupted."""
    epochs, clock = Epochs(tmp_path), Clock()

    def failing_on_the_second_day(
        simulator: Simulator, run: RunRequest, *args: Any, **kw: Any
    ) -> Any:
        if args and args[0] == DAY_S:
            raise RuntimeError("a simulation that fails")
        return delivered_between(simulator, run, *args, **kw)

    monkeypatch.setattr(playback, "delivered_between", failing_on_the_second_day)
    played(epochs, clock)

    _until(lambda: _kept(epochs).status != Status.RUNNING, "the run to end")
    assert _kept(epochs).status == Status.FAILED


def test_a_run_is_asked_for_at_a_seed(short: Simulator, tmp_path: Path) -> None:
    epochs, clock = Epochs(tmp_path), Clock()
    own = SCENARIO_REGISTRY[REFERENCE].random_seed

    def run_id(seed: int | None) -> str:
        return air_through_a_run(short, RunRequest(SHORT, seed=seed))[1]

    seeded = Playback(short, SHORT, seed=7, clock=clock, epochs=epochs)
    plain = Playback(short, SHORT, clock=clock, epochs=epochs)
    explicit = Playback(short, SHORT, seed=own, clock=clock, epochs=epochs)

    assert seeded.run_id == run_id(7) != plain.run_id == run_id(None) == explicit.run_id
    assert (seeded.seed, plain.seed) == (7, None)
    assert seeded.plays(None, 7) and not seeded.plays(None, 8) and seeded.plays(None)
    assert {(r.run_id, r.seed) for r in stored_runs(epochs.objects)} == {
        (seeded.run_id, 7),
        (plain.run_id, None),
        (explicit.run_id, own),
    }
    assert {r.status for r in stored_runs(epochs.objects)} == {Status.QUEUED}


def test_a_playback_started_at_another_seed_starts_over(
    simulator: Simulator, no_playbacks: Callable[[], None], tmp_path: Path
) -> None:
    epochs, clock = Epochs(tmp_path), Clock()
    first = playback.start(simulator, BOX, 10.0, hold=True, clock=clock, epochs=epochs)
    same = playback.start(simulator, BOX, 10.0, hold=True, clock=clock, epochs=epochs)
    other = playback.start(simulator, BOX, 10.0, seed=7, hold=True, clock=clock, epochs=epochs)

    assert same.run_id == first.run_id
    assert other.run_id != first.run_id
    assert [found.run_id for found in simulator.playbacks.all()] == [other.run_id]
    assert playback.playback(simulator, BOX).seed == 7
    # Rearranged, it keeps the seed.
    moved = playback.command(simulator, BOX, PlaybackCommand.RESTART, "default~heater:-1:0.5")
    assert playback.playback(simulator, BOX).seed == 7 and moved.run_id != other.run_id
    # Asked for at another seed alone, it keeps its layout.
    again = playback.start(simulator, BOX, 10.0, seed=8, hold=True, clock=clock, epochs=epochs)
    kept = playback.playback(simulator, BOX)
    assert (kept.seed, kept.layout) == (8, layout_name("default~heater:-1:0.5"))
    assert again.run_id not in (other.run_id, moved.run_id)


def test_the_epochs_kept_by_files_before_are_counted_on_from(tmp_path: Path) -> None:
    legacy = tmp_path / "before"
    legacy.mkdir()
    (legacy / "run_x.epoch").write_text("4\n")
    (legacy / "run_y.epoch").write_text("not a number\n")
    epochs = Epochs(tmp_path / "runs", legacy=legacy)

    assert epochs.next("run_x") == 5
    assert epochs.next("run_y") == 0
    assert epochs.next("run_z") == 0


def test_a_deleted_epochs_number_is_not_given_to_the_next(tmp_path: Path) -> None:
    epochs = Epochs(tmp_path)
    for number in (0, 1):
        epochs.open(
            EpochManifest(
                run_id="run",
                epoch=number,
                scenario_id=BOX,
                seed=None,
                layout="default",
                status=Status.FINISHED,
                duration_s=None,
                created_at=None,
            )
        )

    delete_epoch(epochs.objects, "run", 1)

    assert epochs.next("run") == 2
    delete_epoch(epochs.objects, "run", 0)
    assert epochs.next("run") == 2
