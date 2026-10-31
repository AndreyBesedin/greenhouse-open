"""A run store (P17.3, decisions 0065 and 0066): an epoch's records and
states written whole and read back exactly, a reader that sees only what the
last commit names, and a digest that tells a changed object."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import duckdb
import pytest
from greenhouse_protocol.actions import ActionRef, Harvest, HarvestScope
from greenhouse_protocol.enums import (
    EventSource,
    EventType,
    ObservationQuality,
    ObservationType,
    SourceType,
)
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome, Harvested, OutcomeStatus
from greenhouse_protocol.plan import (
    At,
    ExecutorKind,
    ExecutorRef,
    Principal,
    PrincipalKind,
)
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.checkpoints import Checkpoint, load_openings
from greenhouse_sim.services.replay import day_probes
from greenhouse_sim.services.run_store import (
    OBSERVATIONS,
    EpochManifest,
    EpochStore,
    FolderStore,
    LogEntry,
    Status,
    StoreCorrupt,
    compress,
    decompress,
    epochs,
)
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "reference_greenhouse"
START: Final = datetime(2026, 3, 1, tzinfo=UTC)
OPERATOR: Final = Principal(kind=PrincipalKind.PERSON, id="operator")


def _observations(count: int, first: int = 0) -> list[Observation]:
    return [
        Observation(
            observation_id=f"o{first + i}",
            greenhouse_id="gh",
            plant_id=None if i % 2 else "p1",
            timestamp=START + timedelta(seconds=300 * (first + i)),
            observation_type=ObservationType.AIR_TEMPERATURE_C,
            value=20.0 + ((first + i) * 7919 % 100) / 7.0,
            source=RecordSource(type=SourceType.SIMULATION, source_id="run"),
            sensor_id=f"s{i % 3}" if i % 4 else None,
            delivered_at=START + timedelta(seconds=300 * (first + i) + 60) if i % 5 == 0 else None,
            quality=frozenset({ObservationQuality.CLIPPED}) if i % 3 == 0 else frozenset(),
        )
        for i in range(count)
    ]


def _events(count: int) -> list[Event]:
    return [
        Event(
            event_id=f"e{i}",
            greenhouse_id="gh",
            plant_id=f"p{i}",
            timestamp=START + timedelta(hours=i),
            event_type=EventType.HARVEST,
            source=EventSource.SIMULATION,
            parameters={"harvested_mass_g": 120.5 + i, "harvested_fruit_count": i},
        )
        for i in range(count)
    ]


def _outcomes(count: int) -> list[ActionOutcome]:
    return [
        ActionOutcome(
            outcome_id=f"out{i}",
            greenhouse_id="gh",
            run_id="run",
            epoch=0,
            plan_id="plan",
            revision=1,
            ref=ActionRef(action_id=f"a{i}"),
            action=Harvest(plant_id="p30", scope=HarvestScope.RIPE),
            timing=At(at=START),
            principal=OPERATOR,
            status=OutcomeStatus.EXECUTED,
            due=START,
            started_at=START,
            finished_at=START + timedelta(minutes=1),
            resolved_at=START + timedelta(minutes=1),
            executor=ExecutorRef(kind=ExecutorKind.ROBOT, id="picker"),
            effect=Harvested(fruit_count=4, fresh_mass_g=180.0),
        )
        for i in range(count)
    ]


def _epoch(root: Path, run_id: str = "run_a", epoch: int = 0) -> EpochStore:
    manifest = EpochManifest(run_id=run_id, epoch=epoch, scenario_id=SCENARIO, layout="default")
    return EpochStore.create(FolderStore(root), manifest)


def test_a_folder_store_keeps_named_objects(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    objects.put("a/b/one", b"1")
    objects.put("a/two", b"22")
    objects.put("a/two", b"333")

    assert objects.get("a/two") == b"333"
    assert objects.get("a/none") is None
    assert objects.names("a/") == ["a/b/one", "a/two"]
    assert objects.names("a/b") == ["a/b/one"]
    objects.delete("a/two")
    objects.delete("a/two")
    assert objects.names() == ["a/b/one"]


def test_an_object_is_whole_or_not_there(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    objects = FolderStore(tmp_path)
    objects.put("x", b"old")

    def crash(*_: object) -> None:
        raise OSError("the disk went")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError, match="disk"):
        objects.put("x", b"new, and longer")
    with pytest.raises(OSError, match="disk"):
        objects.put("y", b"new")

    assert objects.get("x") == b"old"
    assert objects.get("y") is None
    assert objects.names() == ["x"]
    assert [p.name for p in tmp_path.iterdir()] == ["x"]


def test_records_come_back_exactly_in_their_order(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    observations, events, outcomes = _observations(40), _events(3), _outcomes(2)

    store.commit(0.0, DAY_S, observations=observations, events=events, outcomes=outcomes)

    assert store.observations().records == observations
    assert store.events().records == events
    assert store.outcomes().records == outcomes
    assert [o.value for o in store.observations().records] == [o.value for o in observations]


def test_a_cursor_counts_across_segments_as_one_log(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    sizes = (5, 0, 7, 4)
    kept: list[Observation] = []
    for number, size in enumerate(sizes):
        batch = _observations(size, first=len(kept))
        kept += batch
        store.commit(number * 100.0, (number + 1) * 100.0, observations=batch)

    for limit in (1, 3, 5, 100):
        read, position = [], 0
        while True:
            page = store.observations(position, limit)
            assert page.next == position + len(page.records)
            read += page.records
            position = page.next
            if not page.has_more:
                break
        assert read == kept
    last = store.observations(sum(sizes))
    assert (last.records, last.next, last.has_more) == ([], sum(sizes), False)
    middle = store.observations(6, 4)
    assert middle.records == kept[6:10] and middle.has_more


def test_a_segments_schema_is_the_logs_and_its_order_the_records(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    store.commit(0.0, DAY_S, observations=_observations(12))
    name = "run_a/0/segments/000000000-000086400/observations.parquet"
    with duckdb.connect() as con:
        described = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{tmp_path / name}')")
        columns = [(row[0], row[1]) for row in described.fetchall()]
    assert columns == [
        (name_, type_.replace("TIMESTAMPTZ", "TIMESTAMP WITH TIME ZONE"))
        for name_, type_ in OBSERVATIONS.columns
    ]
    assert OBSERVATIONS.decode((tmp_path / name).read_bytes()) == _observations(12)


def test_a_reader_sees_only_what_the_last_commit_names(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    store.commit(0.0, 100.0, observations=_observations(3))
    store.commit(100.0, 200.0, observations=_observations(2, first=3))
    objects = FolderStore(tmp_path)
    # A worker that died after its segment, before its commit.
    objects.put("run_a/0/segments/000000200-000000300/observations.parquet", b"not a commit's")

    assert store.frontier_s() == 200.0
    assert [o.observation_id for o in store.observations().records] == [f"o{i}" for i in range(5)]
    # The next commit is the one after the last, whole, over the stray segment.
    again = store.commit(200.0, 300.0, observations=_observations(1, first=5))
    assert again.seq == 2 and store.frontier_s() == 300.0
    assert len(store.observations().records) == 6
    # A commit past a missing one is not seen.
    objects.delete("run_a/0/commits/00000001.json")
    assert store.frontier_s() == 100.0
    assert len(store.observations().records) == 3


def test_a_changed_object_is_told_by_the_digest(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    store.commit(0.0, 100.0, observations=_observations(3), events=_events(1))
    store.commit(100.0, 200.0, observations=_observations(2, first=3))
    store.verify()
    segment = "run_a/0/segments/000000000-000000100/observations.parquet"
    original = FolderStore(tmp_path).get(segment)
    assert original is not None

    FolderStore(tmp_path).put(segment, OBSERVATIONS.encode(_observations(3, first=50)))
    with pytest.raises(StoreCorrupt, match="commit 0"):
        store.observations()
    with pytest.raises(StoreCorrupt, match="commit 0"):
        store.verify()
    FolderStore(tmp_path).put(segment, original)
    store.verify()
    FolderStore(tmp_path).delete(segment)
    with pytest.raises(StoreCorrupt, match="gone"):
        store.observations()


def test_the_log_is_the_commits_and_a_crashs_leftovers_are_overwritten(tmp_path: Path) -> None:
    store = _epoch(tmp_path)
    entry = LogEntry(seq=0, at_s=60.0, by="operator", what={"target": "heating_day", "value": 24})
    store.commit(0.0, 100.0, log=[entry])
    # A line written, whose commit never was.
    objects = FolderStore(tmp_path)
    stray = objects.get("run_a/0/interventions.jsonl") or b""
    objects.put("run_a/0/interventions.jsonl", stray + b'{"seq":1,"at_s":1,"by":"x","what":{}}\n')

    assert store.log() == [entry]
    second = LogEntry(seq=1, at_s=150.0, by="operator", what={"target": "heating_day", "value": 22})
    commit = store.commit(100.0, 200.0, log=[second])
    assert commit.log_position == 2
    assert store.log() == [entry, second]
    store.verify()


def test_an_epoch_has_a_status_and_a_run_its_epochs(tmp_path: Path) -> None:
    first, second = _epoch(tmp_path, epoch=0), _epoch(tmp_path, epoch=1)
    _epoch(tmp_path, run_id="run_b", epoch=0)

    assert first.manifest().status == Status.QUEUED
    second.set_status(Status.RUNNING)
    second.set_status(Status.FINISHED)
    assert second.manifest().status == Status.FINISHED
    assert first.manifest().status == Status.QUEUED
    assert epochs(FolderStore(tmp_path), "run_a") == [0, 1]
    assert epochs(FolderStore(tmp_path), "run_c") == []


def test_a_checkpoint_kept_restores_a_run_that_replays_as_the_straight_run(
    simulator: Simulator, tmp_path: Path
) -> None:
    run = RunRequest(SCENARIO)
    straight = day_probes(simulator, run, 3)
    saved = checkpoints.save_checkpoint(simulator, run, time_s=2 * DAY_S)
    made = checkpoints.checkpoint(simulator, saved.checkpoint_id)
    store = _epoch(tmp_path)

    store.commit(0.0, 2 * DAY_S, checkpoint=compress(made.model_dump_json()))
    found = store.checkpoint_at(2 * DAY_S + 5.0)
    assert found is not None
    data, content_type = found
    assert content_type == "application/json+zstd"
    assert store.checkpoint_at(DAY_S) is None
    restored = Checkpoint.model_validate_json(decompress(data))

    assert restored == made
    with Simulator() as fresh:
        load_openings(fresh)
        checkpoints.upload_checkpoint(fresh, json.loads(restored.model_dump_json()))
        assert day_probes(fresh, run, 3) == straight
