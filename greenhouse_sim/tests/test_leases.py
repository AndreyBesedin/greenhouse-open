"""Who works an epoch (P17.9, decision 0065): a process that says an epoch runs
holds a lease on it, written again while it runs and gone when it ended, so
that an epoch `running` that no one writes can be told from one that is."""

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.services import leases
from greenhouse_sim.services.run_store import EpochManifest, EpochStore, FolderStore, Status

WAIT_S: Final = 30.0


@pytest.fixture
def epoch(tmp_path: Path) -> EpochStore:
    return EpochStore.create(
        FolderStore(tmp_path),
        EpochManifest(
            run_id="run", epoch=0, scenario_id="s", layout="default", created_at=datetime.now(UTC)
        ),
    )


def _lease(epoch: EpochStore) -> str:
    return f"{epoch.run_id}/{epoch.epoch}/{leases.LEASE}"


def _refreshed_at(epoch: EpochStore) -> float:
    data = epoch.objects.get(_lease(epoch))
    assert data is not None
    return float(json.loads(data)["refreshed_at"])


def test_an_epoch_told_to_run_is_held_until_it_is_told_it_ended(epoch: EpochStore) -> None:
    assert not epoch.worked()

    epoch.set_status(Status.RUNNING)
    assert epoch.worked()

    epoch.set_status(Status.INTERRUPTED)
    assert not epoch.worked()
    assert epoch.objects.get(_lease(epoch)) is None


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


def test_an_epoch_told_it_ended_by_another_process_is_not_given_a_lease_again(
    epoch: EpochStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leases, "REFRESH_EVERY_S", 0.02)
    epoch.set_status(Status.RUNNING)
    # Said to have ended by the scheduler, as for a worker that died, which is
    # another process: this one's heartbeat must not write the lease back.
    ended = epoch.manifest().model_copy(update={"status": Status.INTERRUPTED})
    epoch.objects.put(
        f"{epoch.run_id}/{epoch.epoch}/manifest.json", ended.model_dump_json().encode()
    )
    epoch.objects.delete(_lease(epoch))

    time.sleep(0.2)

    assert not epoch.worked()
    assert epoch.objects.get(_lease(epoch)) is None


def test_a_lease_that_is_not_one_is_not_believed(epoch: EpochStore) -> None:
    epoch.objects.put(_lease(epoch), b"not json")

    assert not epoch.worked()
