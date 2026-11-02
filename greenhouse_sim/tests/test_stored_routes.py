"""The runs kept in the run store, as the local API lists, opens and plays them
(P17.4, decision 0065): a scenario's stored runs, an epoch's records after a
cursor by a moment, and the positions a viewer takes over an epoch."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.contracts.consumer import ObservationBatch
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import playback
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    Status,
    StoredRun,
    epochs,
    started_epochs,
)
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.stored_playback import PositionState

SCENARIO: Final = "climate_box"
RUN: Final = "stored-run"
PER_DAY: Final = 4
DAYS: Final = 2


@pytest.fixture
def simulator(tmp_path: Path) -> Iterator[Simulator]:
    """A simulator whose run store holds one epoch of two days of four
    observations each, a day after the one before, all delivered on the hour,
    and finished."""
    objects = FolderStore(tmp_path)
    with Simulator(runs=objects) as made:
        start = run_start(made.catalogue, SCENARIO)
        store = EpochStore.create(
            objects,
            EpochManifest(
                run_id=RUN,
                epoch=0,
                scenario_id=SCENARIO,
                seed=5,
                layout="default",
                status=Status.RUNNING,
                duration_s=DAYS * DAY_S,
                created_at=start,
            ),
        )
        for day in range(DAYS):
            store.commit(
                day * DAY_S,
                (day + 1) * DAY_S,
                observations=[
                    Observation(
                        observation_id=f"o{day}-{i}",
                        greenhouse_id="gh",
                        plant_id=None,
                        timestamp=start + timedelta(seconds=day * DAY_S + 3_600 * (i + 1)),
                        observation_type=ObservationType.AIR_TEMPERATURE_C,
                        value=float(10 * day + i),
                        source=RecordSource(type=SourceType.SIMULATION, source_id=RUN),
                    )
                    for i in range(PER_DAY)
                ],
            )
        store.set_status(Status.FINISHED)
        yield made


def _get(simulator: Simulator, path: str) -> tuple[HTTPStatus, object]:
    response = respond(simulator, "GET", path)
    return response.status, response.body


def _post(simulator: Simulator, path: str) -> tuple[HTTPStatus, object]:
    response = respond(simulator, "POST", path)
    return response.status, response.body


def _ids(body: object) -> list[str]:
    batch = ObservationBatch.model_validate(body)
    return [o.observation_id for o in batch.observations]


def test_a_scenarios_stored_runs_are_listed_as_a_list_shows_them(simulator: Simulator) -> None:
    status, body = _get(simulator, f"/api/scenarios/{SCENARIO}/runs")
    assert status == HTTPStatus.OK and isinstance(body, list)
    (found,) = (StoredRun.model_validate(item) for item in body)
    assert (found.run_id, found.epoch, found.seed, found.status) == (RUN, 0, 5, Status.FINISHED)
    assert (found.frontier_s, found.duration_s, found.progress) == (2 * DAY_S, 2 * DAY_S, 1.0)
    assert found.size_bytes > 0 and found.created_at is not None

    assert _get(simulator, "/api/scenarios/airflow_box/runs") == (HTTPStatus.OK, [])
    status, _ = _get(simulator, "/api/scenarios/no_such_scenario/runs")
    assert status == HTTPStatus.NOT_FOUND
    one = _get(simulator, f"/api/runs/{RUN}/epochs/0")
    assert one == (HTTPStatus.OK, body[0])
    assert _get(simulator, f"/api/runs/{RUN}/epochs/1")[0] == HTTPStatus.NOT_FOUND
    assert _get(simulator, f"/api/runs/{RUN}/epochs/x")[0] == HTTPStatus.BAD_REQUEST


def test_every_stored_run_is_listed_the_newest_started_first(simulator: Simulator) -> None:
    assert simulator.runs is not None
    start = run_start(simulator.catalogue, SCENARIO)
    for run_id, scenario_id, started in (
        ("zz-later", "tomgro_house", start + timedelta(days=1)),
        ("aa-unstarted", SCENARIO, None),
    ):
        EpochStore.create(
            simulator.runs,
            EpochManifest(
                run_id=run_id,
                epoch=0,
                scenario_id=scenario_id,
                seed=None,
                layout="default",
                status=Status.QUEUED,
                duration_s=None,
                created_at=started,
            ),
        )

    status, body = _get(simulator, "/api/runs")

    assert status == HTTPStatus.OK
    assert isinstance(body, list)
    listed = [StoredRun.model_validate(each) for each in body]
    assert [(each.run_id, each.scenario_id) for each in listed] == [
        ("zz-later", "tomgro_house"),
        (RUN, SCENARIO),
        ("aa-unstarted", SCENARIO),
    ]


def test_a_simulator_with_no_run_store_says_so() -> None:
    with Simulator() as without:
        status, body = _get(without, f"/api/scenarios/{SCENARIO}/runs")
    assert status == HTTPStatus.NOT_FOUND
    assert isinstance(body, dict) and "no run store" in str(body["error"])


def test_an_epochs_records_are_read_after_a_cursor_by_a_moment(simulator: Simulator) -> None:
    base = f"/api/runs/{RUN}/epochs/0/observations"
    # By default, everything the epoch delivered: its frontier.
    status, body = _get(simulator, base)
    assert status == HTTPStatus.OK
    assert _ids(body) == [f"o{d}-{i}" for d in range(DAYS) for i in range(PER_DAY)]
    # By a moment: the first day's first two, delivered by two hours in.
    _, early = _get(simulator, f"{base}?t=7200")
    assert _ids(early) == ["o0-0", "o0-1"]
    # Paged: a cursor, a limit, and whether more are delivered.
    _, page = _get(simulator, f"{base}?after=1&limit=3")
    batch = ObservationBatch.model_validate(page)
    assert (_ids(page), batch.after, batch.next, batch.has_more) == (
        ["o0-1", "o0-2", "o0-3"],
        1,
        4,
        True,
    )
    _, last = _get(simulator, f"{base}?after=7&limit=3")
    assert (_ids(last), ObservationBatch.model_validate(last).has_more) == (["o1-3"], False)
    assert _get(simulator, f"/api/runs/{RUN}/epochs/0/events")[0] == HTTPStatus.OK
    assert _get(simulator, f"/api/runs/{RUN}/epochs/0/outcomes")[0] == HTTPStatus.OK
    assert _get(simulator, f"{base}?t=soon")[0] == HTTPStatus.BAD_REQUEST
    assert _get(simulator, f"{base}?after=x")[0] == HTTPStatus.BAD_REQUEST


def test_a_position_is_opened_moved_and_closed(simulator: Simulator) -> None:
    status, body = _post(simulator, f"/api/runs/{RUN}/epochs/0/positions?seconds_per_day=5")
    assert status == HTTPStatus.OK
    state = PositionState.model_validate(body)
    assert (state.time_s, state.playing, state.following, state.seconds_per_day) == (
        0.0,
        False,
        False,
        5.0,
    )
    assert (state.run_id, state.epoch, state.seed, state.frontier_s) == (RUN, 0, 5, 2 * DAY_S)
    here = f"/api/positions/{state.position_id}"
    assert _get(simulator, here) == (HTTPStatus.OK, body)

    status, moved = _post(simulator, f"{here}/seek?t=7200")
    assert status == HTTPStatus.OK and PositionState.model_validate(moved).time_s == 7200.0
    # Its records are the epoch's by its moment.
    _, mine = _get(simulator, f"{here}/observations")
    assert _ids(mine) == ["o0-0", "o0-1"]
    assert _ids(mine) == _ids(_get(simulator, f"/api/runs/{RUN}/epochs/0/observations?t=7200")[1])

    for refused, path in (
        (HTTPStatus.BAD_REQUEST, f"{here}/seek"),
        (HTTPStatus.BAD_REQUEST, f"{here}/seek?t=nope"),
        (HTTPStatus.BAD_REQUEST, f"{here}/seek?t={2 * DAY_S + 1}"),
        (HTTPStatus.BAD_REQUEST, f"{here}/seek?t=-1"),
        (HTTPStatus.BAD_REQUEST, f"{here}/pace"),
        (HTTPStatus.BAD_REQUEST, f"{here}/pace?seconds_per_day=0"),
    ):
        assert _post(simulator, path)[0] == refused, path
    # The refused seeks left it where it was.
    assert PositionState.model_validate(_get(simulator, here)[1]).time_s == 7200.0

    _, paced = _post(simulator, f"{here}/pace?seconds_per_day=2")
    assert PositionState.model_validate(paced).seconds_per_day == 2.0
    _, followed = _post(simulator, f"{here}/follow")
    assert PositionState.model_validate(followed).time_s == 2 * DAY_S
    assert PositionState.model_validate(_post(simulator, f"{here}/play")[1]).following is False
    assert PositionState.model_validate(_post(simulator, f"{here}/pause")[1]).playing is False

    assert _post(simulator, f"{here}/close")[0] == HTTPStatus.OK
    assert _get(simulator, here)[0] == HTTPStatus.NOT_FOUND
    assert _post(simulator, f"{here}/seek?t=1")[0] == HTTPStatus.NOT_FOUND
    assert _post(simulator, "/api/runs/no-such-run/epochs/0/positions")[0] == HTTPStatus.NOT_FOUND


def test_a_route_that_is_not_one_is_not_answered(simulator: Simulator) -> None:
    assert _get(simulator, "/api/positions/x/nothing")[0] == HTTPStatus.NOT_FOUND
    assert _post(simulator, "/api/positions/x/jump")[0] == HTTPStatus.METHOD_NOT_ALLOWED


def test_a_cursor_or_a_limit_that_is_not_one_is_refused_before_anything_is_read(
    simulator: Simulator,
) -> None:
    _, opened = _post(simulator, f"/api/runs/{RUN}/epochs/0/positions")
    position = PositionState.model_validate(opened).position_id
    for kind in ("observations", "events", "outcomes"):
        for base in (f"/api/runs/{RUN}/epochs/0/{kind}", f"/api/positions/{position}/{kind}"):
            for query in ("after=-1", "limit=0", "limit=-3"):
                status, body = _get(simulator, f"{base}?{query}")
                assert status == HTTPStatus.BAD_REQUEST, (base, query)
                assert isinstance(body, dict) and "error" in body
    # A limit above the most a batch holds is held to it, not refused.
    assert _get(simulator, f"/api/runs/{RUN}/epochs/0/observations?limit=1000000")[0] == (
        HTTPStatus.OK
    )


class Listing(FolderStore):
    """A folder store that notes the folders it was asked to list."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.listed: list[str] = []

    def names(self, prefix: str = "") -> list[str]:
        self.listed.append(prefix)
        return super().names(prefix)

    def children(self, prefix: str = "") -> list[str]:
        self.listed.append(prefix)
        return super().children(prefix)


def test_one_epoch_is_looked_up_without_reading_the_others(tmp_path: Path) -> None:
    objects = Listing(tmp_path)
    for run_id in ("first-run", "second-run"):
        EpochStore.create(
            objects,
            EpochManifest(run_id=run_id, epoch=0, scenario_id=SCENARIO, layout="default"),
        ).commit(0.0, DAY_S)
    with Simulator(runs=objects) as made:
        objects.listed.clear()
        status, body = _get(made, "/api/runs/second-run/epochs/0")
        assert status == HTTPStatus.OK and isinstance(body, dict)
        assert body["run_id"] == "second-run"
        assert objects.listed and all(p.startswith("second-run/") for p in objects.listed)

        objects.listed.clear()
        assert _get(made, "/api/runs/missing-run/epochs/0")[0] == HTTPStatus.NOT_FOUND
        assert _get(made, "/api/runs/first-run/epochs/7")[0] == HTTPStatus.NOT_FOUND
        assert all(p.startswith(("missing-run/", "first-run/")) for p in objects.listed)


def test_a_stored_epoch_is_deleted_with_its_positions_and_keeps_its_number(
    simulator: Simulator,
) -> None:
    assert simulator.runs is not None
    _, opened = _post(simulator, f"/api/runs/{RUN}/epochs/0/positions")
    position_id = PositionState.model_validate(opened).position_id

    status, body = _post(simulator, f"/api/runs/{RUN}/epochs/0/delete")

    assert (status, body) == (HTTPStatus.OK, {"deleted": f"{RUN}/0"})
    assert _get(simulator, f"/api/scenarios/{SCENARIO}/runs") == (HTTPStatus.OK, [])
    assert _get(simulator, f"/api/runs/{RUN}/epochs/0")[0] == HTTPStatus.NOT_FOUND
    assert _get(simulator, f"/api/positions/{position_id}")[0] == HTTPStatus.NOT_FOUND
    # The epoch is gone, and its number is not given to another (decision 0040).
    assert epochs(simulator.runs, RUN) == []
    assert started_epochs(simulator.runs, RUN) == [0]
    # By a mark of its own: a store of objects has no folder to keep the number.
    assert simulator.runs.names(f"{RUN}/0/") == [f"{RUN}/0/deleted.json"]
    assert _post(simulator, f"/api/runs/{RUN}/epochs/0/delete")[0] == HTTPStatus.NOT_FOUND


def test_an_epoch_whose_producer_is_gone_is_deleted_though_its_status_says_running(
    simulator: Simulator,
) -> None:
    assert simulator.runs is not None
    EpochStore.create(
        simulator.runs,
        EpochManifest(
            run_id="left-running",
            epoch=0,
            scenario_id=SCENARIO,
            seed=None,
            layout="default",
            status=Status.RUNNING,
            duration_s=None,
            created_at=None,
        ),
    )

    status, _ = _post(simulator, "/api/runs/left-running/epochs/0/delete")

    assert status == HTTPStatus.OK
    assert started_epochs(simulator.runs, "left-running") == [0]


def test_an_epoch_a_playback_is_working_on_is_refused_until_it_stops(
    simulator: Simulator, no_playbacks: Callable[[], None]
) -> None:
    assert simulator.runs is not None
    try:
        started = respond(simulator, "POST", f"/api/scenarios/{SCENARIO}/playback/start?hold=true")
        assert started.status == HTTPStatus.OK
        working = playback.playback(simulator, SCENARIO).state()
        refused = _post(simulator, f"/api/runs/{working.run_id}/epochs/{working.epoch}/delete")
        no_playbacks()
        allowed = _post(simulator, f"/api/runs/{working.run_id}/epochs/{working.epoch}/delete")
    finally:
        no_playbacks()

    assert refused[0] == HTTPStatus.CONFLICT
    assert "being computed" in str(refused[1])
    assert allowed[0] == HTTPStatus.OK


def test_a_run_is_started_at_a_seed_and_a_seed_that_is_not_one_is_refused(
    simulator: Simulator, no_playbacks: Callable[[], None]
) -> None:
    path = f"/api/scenarios/{SCENARIO}/playback/start?hold=true"
    try:
        plain = respond(simulator, "POST", path)
        seeded = respond(simulator, "POST", f"{path}&seed=7")
        refused = respond(simulator, "POST", f"{path}&seed=seven")
    finally:
        no_playbacks()

    assert plain.status == seeded.status == HTTPStatus.OK
    assert isinstance(plain.body, dict) and isinstance(seeded.body, dict)
    assert plain.body["run_id"] != seeded.body["run_id"]
    assert refused.status == HTTPStatus.BAD_REQUEST


def test_a_run_started_over_the_api_is_kept_and_listed_with_its_seed(
    simulator: Simulator, no_playbacks: Callable[[], None]
) -> None:
    try:
        started = respond(
            simulator, "POST", f"/api/scenarios/{SCENARIO}/playback/start?hold=true&seed=7"
        )
        assert started.status == HTTPStatus.OK
        status, listed = _get(simulator, f"/api/scenarios/{SCENARIO}/runs")
    finally:
        no_playbacks()

    assert status == HTTPStatus.OK
    assert isinstance(listed, list)
    seeded = [StoredRun.model_validate(each) for each in listed if each["seed"] == 7]
    assert len(seeded) == 1
    assert seeded[0].status in (Status.QUEUED, Status.RUNNING)
    assert seeded[0].scenario_id == SCENARIO
