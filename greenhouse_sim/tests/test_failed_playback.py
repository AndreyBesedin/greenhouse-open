"""A playback that failed stays kept, so that whoever reads it learns it failed,
and does not stand in the way of its scenario: a new start, or a restart, plays
the run again as a new playback and its next epoch. Its work is failed here by
`work_day`, with no thread to race against: it has failed by the time it is
kept, as one that failed while it played has."""

import sys
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.services import playback
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackFailed
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    ObjectStore,
    Status,
    started_epochs,
    stored_run,
)
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

BOX: Final = "failed_box"
ONE_SENSOR: Final = ("temperature_front",)
START_HELD: Final = f"/api/scenarios/{BOX}/playback/start?hold=true"
RESTART: Final = f"/api/scenarios/{BOX}/playback/restart"
READ: Final = f"/api/scenarios/{BOX}/playback"
DELIVERED: Final = "greenhouse_sim.services.playback.delivered_between"
# A target change of the run that failed.
TARGET: Final = (60.0, "heating_day", 24.0)


def _broken(*_: object, **__: object) -> None:
    raise ArithmeticError("a numerical failure")


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Simulator]:
    box = cut("climate_box", days=2, sensors=ONE_SENSOR, greenhouse_id=BOX)
    with simulator_of(box, runs=FolderStore(tmp_path / "runs")) as made:
        yield made


def _store(server: Simulator) -> ObjectStore:
    assert server.runs is not None
    return server.runs


def _failed(
    simulator: Simulator,
    monkeypatch: pytest.MonkeyPatch,
    *,
    targets: tuple[tuple[float, str, float], ...] = (),
) -> Playback:
    """The scenario's playback, failed, and its epoch said so in the store if it
    keeps one, as its thread says it as it ends."""
    epochs = None if simulator.runs is None else Epochs(objects=simulator.runs)
    with monkeypatch.context() as patch:
        patch.setattr(DELIVERED, _broken)
        failed = Playback(simulator, BOX, epochs=epochs, targets=targets)
        assert not failed.work_day(0)
    failed.keep()
    simulator.playbacks.made_once(BOX, lambda _: failed)
    return failed


def test_a_start_after_a_failure_gets_a_new_playback_and_the_failed_one_still_says_why(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _failed(server, monkeypatch)
    with pytest.raises(PlaybackFailed):
        respond(server, "GET", READ)

    started = respond(server, "POST", START_HELD)

    assert started.status == HTTPStatus.OK
    state = playback.state(server, BOX)
    assert (state.run_id, state.epoch) == (failed.run_id, 1)
    assert respond(server, "GET", READ).status == HTTPStatus.OK
    assert playback.playback(server, BOX) is not failed
    assert playback.playback(server, BOX).working
    # Whoever held the one that failed, and whoever lists its epoch.
    with pytest.raises(PlaybackFailed):
        failed.state()
    kept = stored_run(_store(server), failed.run_id, 0)
    assert kept.status == Status.FAILED
    assert kept.reason is not None and "ArithmeticError" in kept.reason
    assert stored_run(_store(server), failed.run_id, 1).status == Status.RUNNING

    # The new one is the scenario's playback now: a start finds it.
    assert respond(server, "POST", START_HELD).status == HTTPStatus.OK
    assert playback.state(server, BOX).epoch == 1
    assert started_epochs(_store(server), failed.run_id) == [0, 1]


def test_a_restart_after_a_failure_gets_a_new_playback_and_leaves_no_epoch_nobody_works(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _failed(server, monkeypatch)

    restarted = respond(server, "POST", RESTART)

    assert restarted.status == HTTPStatus.OK
    assert playback.playback(server, BOX) is not failed
    assert playback.playback(server, BOX).working
    assert playback.state(server, BOX).epoch == 1
    assert started_epochs(_store(server), failed.run_id) == [0, 1]
    assert stored_run(_store(server), failed.run_id, 0).status == Status.FAILED


def test_with_no_store_the_new_playback_is_a_new_epoch_without_the_failed_one_s_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heated = cut("reference_greenhouse", days=2, plants=(1, 1), greenhouse_id=BOX)
    with simulator_of(heated) as simulator:
        failed = _failed(simulator, monkeypatch, targets=(TARGET,))
        assert respond(simulator, "POST", START_HELD).status == HTTPStatus.OK
        state = playback.state(simulator, BOX)
    # A consumer's cursor of the epoch before is told the epoch changed.
    assert (state.run_id, state.epoch) == (failed.run_id, 1)
    assert state.targets == []


def test_a_start_whose_own_playback_fails_at_once_is_not_started_again(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fails_as_it_begins(self: Playback) -> None:
        assert not self.work_day(0)

    monkeypatch.setattr(DELIVERED, _broken)
    monkeypatch.setattr(Playback, "begin", fails_as_it_begins)

    with pytest.raises(PlaybackFailed):
        respond(server, "POST", START_HELD)

    run_id = playback.playback(server, BOX).run_id
    assert started_epochs(_store(server), run_id) == [0]


def test_a_failure_in_a_replaced_playback_still_ending_keeps_no_delete_from_answering(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = EpochStore.create(
        _store(server),
        EpochManifest(
            run_id="other",
            epoch=0,
            scenario_id=BOX,
            layout="default",
            status=Status.FINISHED,
        ),
    )
    failed = _failed(server, monkeypatch)
    assert respond(server, "POST", RESTART).status == HTTPStatus.OK
    # Its thread is at its last lines: its failure is told, and it has not ended.
    monkeypatch.setattr(Playback, "working", property(lambda found: found is failed))
    assert server.playbacks.retiring() == [failed]

    deleted = respond(server, "POST", f"/api/runs/{other.run_id}/epochs/0/delete")
    assert deleted.status == HTTPStatus.OK

    # What it may still be writing is not removed under it.
    refused = respond(server, "POST", f"/api/runs/{failed.run_id}/epochs/0/delete")
    assert refused.status == HTTPStatus.CONFLICT
