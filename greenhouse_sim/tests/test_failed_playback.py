"""A playback that failed says why to whoever reads it, in the words its epoch
keeps. Its work is failed here by `work_day`, with no thread to race against: it
has failed by the time it is read, as one that failed while it played has."""

import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackFailed
from greenhouse_sim.services.run_store import (
    FolderStore,
    ObjectStore,
    stored_run,
)
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

BOX: Final = "failed_box"
ONE_SENSOR: Final = ("temperature_front",)
DELIVERED: Final = "greenhouse_sim.services.playback.delivered_between"


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


def _failed(simulator: Simulator, monkeypatch: pytest.MonkeyPatch) -> Playback:
    """The scenario's playback, failed, and its epoch said so in the store, as
    its thread says it as it ends."""
    with monkeypatch.context() as patch:
        patch.setattr(DELIVERED, _broken)
        failed = Playback(simulator, BOX, epochs=Epochs(objects=_store(simulator)))
        assert not failed.work_day(0)
    failed.keep()
    return failed


def test_a_failed_playback_says_why_as_its_epoch_keeps_it_in_the_words_any_reader_gets(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _failed(server, monkeypatch)
    reason = stored_run(_store(server), failed.run_id, 0).reason
    assert reason == "its run could not be worked out (ArithmeticError)"

    with pytest.raises(PlaybackFailed) as read:
        failed.state()
    assert read.value.message == reason


def test_a_failure_a_service_said_is_answered_in_its_words_as_any_other_failure(
    server: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(*_: object, **__: object) -> None:
        raise NotFound("no such run")

    failed = Playback(server, BOX, epochs=Epochs(objects=_store(server)))
    with monkeypatch.context() as patch:
        patch.setattr(DELIVERED, refused)
        assert not failed.work_day(0)

    # Not a run not found, which would say it was never started.
    with pytest.raises(PlaybackFailed) as read:
        failed.state()
    assert read.value.message == "no such run"


def test_a_failure_is_logged_once_as_it_happens_and_not_at_each_read(
    server: Simulator, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="greenhouse_sim.services.playback"):
        failed = _failed(server, monkeypatch)
        for _ in range(3):
            with pytest.raises(PlaybackFailed):
                failed.state()

    assert [record.exc_info is not None for record in caplog.records] == [True]
