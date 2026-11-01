"""A stored epoch played back as a position (P17.4, decision 0065): where a
viewer stands over an epoch kept in the run store. It reads what the epoch
delivered by its moment, seeks anywhere up to the frontier, follows it, and
changes nothing the epoch holds or a consumer reads."""

import threading
import time
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.observation import Observation

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.checkpoints import load_openings
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand, delivered
from greenhouse_sim.services.replay import day_probes
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    Status,
    stored_runs,
)
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.stored_playback import Position, StoredEpoch

REFERENCE: Final = "reference_greenhouse"
STORED: Final = "reference_greenhouse_stored"
DAYS: Final = 3
EVERY_S: Final = 300.0
ALL: Final = 10**6
WAIT_S: Final = 240.0


class Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _register(simulator: Simulator) -> None:
    config = SCENARIO_REGISTRY[REFERENCE].model_copy(
        update=dict(greenhouse_id=STORED, duration_days=DAYS)
    )
    simulator.catalogue.register(config)


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


class Kept:
    """A run of three days played to its end and kept: its simulator, the
    store it was kept in, the playback that kept it, and its epoch."""

    def __init__(self, simulator: Simulator, epochs: Epochs, played: Playback, epoch: int) -> None:
        self.simulator, self.epochs, self.played, self.epoch = simulator, epochs, played, epoch
        self.run_id = played.run_id

    def opened(self, clock: Callable[[], float] = time.monotonic) -> Position:
        return self.simulator.positions.open(
            self.simulator, self.epochs.objects, self.run_id, self.epoch, clock=clock
        )


@pytest.fixture(scope="module")
def kept(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Kept]:
    with Simulator() as simulator:
        load_openings(simulator)
        _register(simulator)
        epochs, clock = Epochs(tmp_path_factory.mktemp("runs")), Clock()
        played = Playback(
            simulator, STORED, seconds_per_day=10.0, every_s=EVERY_S, clock=clock, epochs=epochs
        )
        played.begin()
        try:
            assert played.wait_for(DAYS, timeout_s=WAIT_S)
            played.command(PlaybackCommand.PLAY)
            clock.now += 10.0 * DAYS

            def finished() -> bool:
                return any(r.status == Status.FINISHED for r in stored_runs(epochs.objects, STORED))

            _until(finished, "the run to be kept whole")
            (found,) = stored_runs(epochs.objects, STORED)
            yield Kept(simulator, epochs, played, found.epoch)
        finally:
            played.stop()


class Listing(FolderStore):
    """A folder store that notes what it was asked to list."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.listed: list[str] = []

    def names(self, prefix: str = "") -> list[str]:
        self.listed.append(prefix)
        return super().names(prefix)


def test_the_runs_of_a_store_are_found_by_their_folders(kept: Kept) -> None:
    objects = Listing(kept.epochs.folder)
    (found,) = stored_runs(objects, STORED)
    assert (found.run_id, found.status) == (kept.run_id, Status.FINISHED)
    # Nothing listed every object of the store: only a run's commits.
    assert "" not in objects.listed
    assert all(prefix.endswith("/commits/") for prefix in objects.listed)
    assert stored_runs(objects, "no_such_scenario") == []


def test_a_position_reads_what_the_epoch_delivered_by_its_moment(kept: Kept) -> None:
    store = EpochStore(kept.epochs.objects, kept.run_id, kept.epoch)
    everything = store.observations(0, ALL).records
    start = kept.played.start
    position = kept.opened()
    for moment_s in (0.0, 3_600.0, DAY_S - 1.0, DAY_S, 1.5 * DAY_S, DAYS * DAY_S):
        position.seek(moment_s)
        expected = [r for r in everything if delivered(r) <= start + timedelta(seconds=moment_s)]
        got = position.observations(0, ALL)
        assert list(got.records) == expected and not got.has_more, moment_s
        # Read in pages, a cursor gives the same.
        paged: list[Observation] = []
        cursor = 0
        while True:
            page = position.observations(cursor, 700)
            paged += page.records
            cursor = page.next
            if not page.has_more:
                break
        assert paged == expected, moment_s
    assert position.events(0, ALL).records == tuple(store.events(0, ALL).records)
    outcomes = position.outcomes(0, ALL)
    assert outcomes.records == tuple(store.outcomes(0, ALL).records) and not outcomes.has_more


def test_a_position_seeks_back_and_forth_over_a_finished_epoch(kept: Kept) -> None:
    position = kept.opened()
    assert position.state().time_s == 0.0
    for moment_s in (2 * DAY_S, 0.5 * DAY_S, DAYS * DAY_S, 0.0, 1_234.5):
        state = position.seek(moment_s)
        assert (state.time_s, state.day, state.following) == (
            moment_s,
            int(moment_s // DAY_S),
            False,
        )
        assert state.simulated_now == kept.played.start + timedelta(seconds=moment_s)
    for refused in (-1.0, DAYS * DAY_S + 1.0):
        with pytest.raises(InvalidRequest, match="between the run's start and its frontier"):
            position.seek(refused)
    assert position.state().time_s == 1_234.5
    # A position that follows the frontier stops following when it is moved.
    assert position.follow().following and position.state().time_s == DAYS * DAY_S
    moved = position.seek(DAY_S)
    assert (moved.following, moved.time_s) == (False, DAY_S)


def test_two_positions_over_one_epoch_do_not_affect_each_other_or_the_epoch(kept: Kept) -> None:
    store = EpochStore(kept.epochs.objects, kept.run_id, kept.epoch)
    before = ([c.digest for c in store.commits()], store.manifest())
    first, second = kept.opened(), kept.opened()
    assert first.position_id != second.position_id
    first.seek(2 * DAY_S)
    second.seek(0.5 * DAY_S)
    assert (first.state().time_s, second.state().time_s) == (2 * DAY_S, 0.5 * DAY_S)
    second.play()
    first.follow()
    assert (first.state().following, second.state().following) == (True, False)
    assert second.state().playing and not first.state().playing
    assert ([c.digest for c in store.commits()], store.manifest()) == before
    store.verify()
    assert kept.simulator.positions.get(first.position_id) is first
    kept.simulator.positions.close(first.position_id)
    with pytest.raises(NotFound):
        kept.simulator.positions.get(first.position_id)
    assert kept.simulator.positions.get(second.position_id) is second


def test_a_seek_moves_nothing_a_consumer_reads(kept: Kept) -> None:
    def read() -> tuple[object, ...]:
        return (
            kept.played.records_after(0, ALL).records,
            kept.played.events_after(0, ALL).records,
            kept.played.outcomes_after(0, ALL)[0].outcomes,
            kept.played.state(),
        )

    before = read()
    position = kept.opened()
    for moment_s in (0.5 * DAY_S, 2 * DAY_S, 0.0):
        position.seek(moment_s)
    position.follow()
    assert read() == before


def test_a_position_plays_by_its_pace_and_stops_at_the_end_of_a_finished_epoch(
    kept: Kept,
) -> None:
    clock = Clock()
    position = kept.opened(clock)
    position.set_pace(10.0)
    assert not position.state().playing
    clock.now += 100.0
    assert position.state().time_s == 0.0  # paused: nothing moves
    assert position.play().playing
    clock.now += 5.0
    assert position.state().time_s == pytest.approx(0.5 * DAY_S)
    position.pause()
    clock.now += 50.0
    assert position.state().time_s == pytest.approx(0.5 * DAY_S)
    position.play()
    clock.now += 1_000.0
    ended = position.state()
    assert (ended.time_s, ended.playing) == (DAYS * DAY_S, False)
    assert not position.play().playing  # at the end of a finished epoch
    with pytest.raises(InvalidRequest, match="seconds_per_day"):
        position.set_pace(0.0)


def test_an_epoch_that_is_not_in_the_store_is_not_found(kept: Kept) -> None:
    with pytest.raises(NotFound):
        kept.simulator.positions.open(kept.simulator, kept.epochs.objects, kept.run_id, 99)
    with pytest.raises(NotFound):
        kept.simulator.positions.open(kept.simulator, kept.epochs.objects, "no-such-run", 0)


@pytest.fixture
def computing(tmp_path: Path) -> Iterator[tuple[Simulator, EpochStore]]:
    """An epoch of a run of three days with only its first day committed and
    its status running, as a worker leaves it while it computes."""
    with Simulator() as simulator:
        _register(simulator)
        objects = FolderStore(tmp_path)
        store = EpochStore.create(
            objects,
            EpochManifest(
                run_id="computing",
                epoch=0,
                scenario_id=STORED,
                layout="default",
                status=Status.RUNNING,
                duration_s=DAYS * DAY_S,
            ),
        )
        store.commit(0.0, DAY_S)
        yield simulator, store


def test_a_position_cannot_pass_the_frontier_of_an_epoch_still_computing(
    computing: tuple[Simulator, EpochStore],
) -> None:
    simulator, store = computing
    clock = Clock()
    position = simulator.positions.open(simulator, store.objects, "computing", 0, clock=clock)
    assert position.state().frontier_s == DAY_S
    with pytest.raises(InvalidRequest, match="frontier"):
        position.seek(DAY_S + 1.0)
    position.seek(DAY_S)

    # Played on, it waits at the frontier, and goes on when the worker commits.
    position.seek(0.5 * DAY_S)
    position.set_pace(1.0)
    position.play()
    clock.now += 10.0
    waiting = position.state()
    assert (waiting.time_s, waiting.playing) == (DAY_S, True)
    store.commit(DAY_S, 2 * DAY_S)
    clock.now += 0.5
    assert position.state().time_s == pytest.approx(1.5 * DAY_S)

    # Following, it stays at the frontier as the worker moves it.
    other = simulator.positions.open(simulator, store.objects, "computing", 0, clock=clock)
    assert other.follow().time_s == 2 * DAY_S
    store.commit(2 * DAY_S, 3 * DAY_S)
    assert other.state().time_s == 3 * DAY_S
    store.set_status(Status.FINISHED)
    assert position.state().frontier_s == 3 * DAY_S


def test_no_checkpoint_is_restored_before_the_first_is_kept(
    computing: tuple[Simulator, EpochStore],
) -> None:
    simulator, store = computing
    assert StoredEpoch(simulator, store.objects, "computing", 0).restore_near(0.5 * DAY_S) is None


def _kept_days(simulator: Simulator) -> list[int]:
    """The days of the states kept for the stored scenario's run."""
    return sorted(kept.day for _, kept in simulator.states.values() if kept.house[0] == STORED)


@pytest.mark.slow
def test_seeking_restores_the_nearest_checkpoint_and_draws_the_straight_runs_moment(
    kept: Kept, tmp_path: Path
) -> None:
    straight = day_probes(kept.simulator, RunRequest(STORED), DAYS)
    # Another simulator, which has worked no day of this run out: a seek gives
    # it the checkpoint, and it draws the run's last day as the straight run did.
    with Simulator() as other:
        load_openings(other)
        _register(other)
        assert not _kept_days(other)
        position = other.positions.open(other, kept.epochs.objects, kept.run_id, kept.epoch)
        state = position.seek(2.5 * DAY_S)
        assert state.time_s == 2.5 * DAY_S
        assert _kept_days(other) == [2]
        probes = day_probes(other, position.epoch.run(), DAYS)
        assert [p.digest for p in probes] == [p.digest for p in straight]
