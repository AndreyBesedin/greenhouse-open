"""The services the local API is an interface to: what each answers, and the
typed error it raises for each case it refuses, with no HTTP in sight."""

from collections.abc import Iterator

import pytest

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SCHEMA_VERSION, SceneEntityKind
from greenhouse_sim.services import scenarios, system
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.live import (
    SPEEDS,
    InvalidSpeed,
    LiveCommand,
    LiveRuns,
    LiveState,
)
from greenhouse_sim.services.scenarios import SceneChanges


def test_the_system_says_it_is_up_and_what_it_is() -> None:
    assert system.health().status == "ok"
    version = system.version()
    assert (version.simulator, version.scene_schema_version) == ("greenhouse-sim", SCHEMA_VERSION)
    assert version.version


def test_every_registered_scenario_is_summarised_with_its_layouts() -> None:
    summaries = {summary.id: summary for summary in scenarios.scenario_summaries()}

    assert set(summaries) == set(SCENARIO_REGISTRY)
    assert summaries["gh_001"].layouts == ["default", "benches"]
    assert summaries["gh_001"].plants == 40


def test_an_unregistered_scenario_is_not_found() -> None:
    with pytest.raises(NotFound, match="no scenario 'gh_404'"):
        scenarios.scenario("gh_404")
    with pytest.raises(NotFound):
        scenarios.initial_scene("gh_404")
    with pytest.raises(NotFound):
        scenarios.layout("gh_404")


def test_a_crop_is_named_by_its_scenario_and_place() -> None:
    names = scenarios.plant_ids(SCENARIO_REGISTRY["gh_demo"])

    assert names == [f"gh_demo_plant_{i:03d}" for i in range(1, 7)]


def test_a_scene_without_changes_is_the_scenario_as_registered() -> None:
    config = SCENARIO_REGISTRY["gh_001"]
    scene = scenarios.initial_scene("gh_001")
    plants = [e for e in scene.entities if e.kind == SceneEntityKind.PLANT]

    assert scenarios.changed(config, SceneChanges()) is config
    assert (scene.greenhouse_id, scene.simulated_day, len(plants)) == ("gh_001", 0, 40)


def test_a_scene_shows_the_scenario_changed_as_asked() -> None:
    changes = SceneChanges(
        layout="benches", envelope={"length": 12.0}, openings={"roof_vent_1": 1.0}
    )
    scene = scenarios.initial_scene("gh_001", changes)
    kinds = {entity.kind for entity in scene.entities}
    vent = next(e for e in scene.entities if e.entity_id == "gh_001_roof_vent_1")
    bounds = next(e for e in scene.entities if e.kind == SceneEntityKind.GREENHOUSE_BOUNDS)

    assert SceneEntityKind.BENCH in kinds and SceneEntityKind.CROP_GUTTER not in kinds
    assert vent.properties["open_fraction"] == 1.0
    assert bounds.shape.shape == "box" and bounds.shape.size_x == 12.0


@pytest.mark.parametrize(
    ("changes", "error", "reason"),
    [
        (SceneChanges(layout="hydroponic"), NotFound, "gh_001 has no layout 'hydroponic'"),
        (SceneChanges(layout="../gh_002/default"), NotFound, "has no layout"),
        (SceneChanges(envelope={"height": 4.0}), InvalidRequest, "the envelope has no 'height'"),
        (SceneChanges(openings={"skylight": 1.0}), InvalidRequest, "has no opening 'skylight'"),
        (SceneChanges(envelope={"ridge_height": 2.0}), InvalidRequest, "no such greenhouse"),
        # Shrunk, the greenhouse no longer holds its layout.
        (SceneChanges(envelope={"length": 5.0}), InvalidRequest, "outside the greenhouse"),
        (
            SceneChanges(layout="benches", envelope={"length": 7.0}),
            InvalidRequest,
            "outside the greenhouse",
        ),
        (SceneChanges(openings={"roof_vent_1": 1.5}), InvalidRequest, "no such greenhouse"),
    ],
)
def test_a_change_that_cannot_be_made_is_refused_with_its_reason(
    changes: SceneChanges, error: type[ServiceError], reason: str
) -> None:
    with pytest.raises(error, match=reason) as refused:
        scenarios.initial_scene("gh_001", changes)

    assert reason in refused.value.message


def test_a_layout_is_given_as_its_file_holds_it() -> None:
    default, benches = scenarios.layout("gh_001"), scenarios.layout("gh_001", "benches")

    rows = benches["crop_rows"]
    assert isinstance(rows, dict)
    support = rows["support"]

    assert default["$schema"] == benches["$schema"]
    assert isinstance(support, dict) and support["kind"] == "bench"


@pytest.fixture
def runs() -> Iterator[LiveRuns]:
    runs = LiveRuns(seconds_per_day=60.0)
    yield runs
    runs.stop()


@pytest.mark.parametrize(
    ("command", "day", "playing"),
    [
        (LiveCommand.PAUSE, 0, False),
        (LiveCommand.PLAY, 0, True),
        (LiveCommand.STEP, 1, True),
        (LiveCommand.RESET, 0, True),
    ],
)
def test_a_live_command_answers_with_the_runs_new_state(
    runs: LiveRuns, command: LiveCommand, day: int, playing: bool
) -> None:
    state = runs.command("gh_demo", command)

    assert type(state) is LiveState
    assert (state.day, state.playing) == (day, playing)


def test_a_live_run_plays_at_the_speeds_it_offers_and_no_other(runs: LiveRuns) -> None:
    assert [runs.set_speed("gh_demo", speed).speed for speed in SPEEDS] == list(SPEEDS)
    with pytest.raises(InvalidSpeed, match="multiplier must be one of 0.25, 0.5, 1, 2, 4, 8"):
        runs.set_speed("gh_demo", 3.0)
    assert issubclass(InvalidSpeed, InvalidRequest)


def test_an_unregistered_scenario_has_no_live_run(runs: LiveRuns) -> None:
    with pytest.raises(NotFound, match="no scenario 'gh_404'"):
        runs.run("gh_404")
    with pytest.raises(NotFound):
        runs.command("gh_404", LiveCommand.PAUSE)
    with pytest.raises(NotFound):
        runs.set_speed("gh_404", 2.0)


def test_a_frame_states_its_run_without_its_scene(runs: LiveRuns) -> None:
    frame = runs.run("gh_demo").latest()

    assert frame.state().model_dump() == frame.model_dump(exclude={"snapshot"})
