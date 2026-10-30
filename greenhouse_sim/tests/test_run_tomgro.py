"""A scenario whose rows grow Reduced-State TOMGRO, run (P14.10, decisions
0060 and 0062): the services grow it by area, on each row's scope, in the
house's air and the light above each row, hour by hour; keep it in a
checkpoint and carry on from it; and ask nothing of it they ask of plants.
"""

import math
import re
from collections.abc import Iterator
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind
from pydantic import ValidationError

from greenhouse_sim.biology.tomato.tomgro.parameters import INITIAL_STATE, TomgroParameters
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.scopes import AreaBasis
from greenhouse_sim.ground_truth import ground_truth
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scene.snapshot import SceneEntityKind
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.crop import crop_scene, of_plants, plants_light, scenario_crop
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.crop_models import AreaCropState, TomgroCropState, registration
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest, crop_model_refusal
from greenhouse_sim.services.scenarios import initial_scene, plant_ids
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.world.scopes import converted, row_scopes

# The climate box, its rows growing Reduced-State TOMGRO.
CONFIG: Final = ScenarioConfig.model_validate(
    SCENARIO_REGISTRY["climate_box"].model_dump()
    | {
        "greenhouse_id": "tomgro_box",
        "crop_model": "reduced_tomgro",
        "crop": {"kind": "reduced_tomgro"},
    }
)
RUN: Final = RunRequest("tomgro_box")
ROWS: Final = [scope.scope_id for scope in row_scopes(CONFIG.layout, CONFIG.envelope)]


def _simulator() -> Simulator:
    """A simulator that knows the scenario."""
    simulator = Simulator(Catalogue())
    simulator.catalogue.register(CONFIG)
    return simulator


@pytest.fixture(scope="module")
def grown() -> Iterator[Simulator]:
    with _simulator() as simulator:
        yield simulator


def test_its_run_grows_its_crop_by_area_on_each_row(grown: Simulator) -> None:
    crop = scenario_crop(grown, RUN)
    assert not of_plants(crop)
    rung = registration(CONFIG).area
    assert rung is not None
    model = rung.rung(CONFIG)

    instances = crop.instances_on(3)
    assert [instance.scope_id for instance in instances] == ROWS == ["row_1", "row_2"]
    for instance in instances:
        expected = INITIAL_STATE
        # Its model's step is a day.
        for step in range(3):
            expected = model.live_step(expected, crop.course(instance.scope_id, step))
        assert instance.state == expected
        # Its nodes grow with the air's warmth; in the box's cold, dim air its
        # dry weight respires more than it gains.
        assert instance.state.n > INITIAL_STATE.n
    # Each hour of a row's day is the house's air through it.
    _, run_id = air_through_a_run(grown, RUN)
    assert len(crop.course("row_1", 0).hours) == 24 and run_id


def test_its_scene_draws_each_rows_canopy_and_no_plant_it_does_not_have(
    grown: Simulator,
) -> None:
    drawn = crop_scene(grown, RUN, time_s=3 * DAY_S).entities
    crop = scenario_crop(grown, RUN)
    assert not of_plants(crop)
    instances = crop.instances_on(3)

    assert [entity.kind for entity in drawn] == [SceneEntityKind.CANOPY] * len(ROWS)
    for entity, instance in zip(drawn, instances, strict=True):
        assert entity.properties["scope"] == instance.scope_id
        assert entity.properties["lai"] == instance.state.lai
        assert entity.properties["model"] == "reduced_tomgro"
        assert entity.properties["proxy"] is True and entity.properties["prediction"] is True
        # As dense as the share of the light its leaves take over the ground
        # it is drawn on: its leaf area per m² of floor, over its cultivated
        # ground.
        scope = {scope.scope_id: scope for scope in crop.scopes}[instance.scope_id]
        on_its_ground = converted(instance.state.lai, scope, AreaBasis.FLOOR, AreaBasis.CULTIVATED)
        assert on_its_ground > instance.state.lai
        assert entity.properties["canopy_lai"] == pytest.approx(on_its_ground, rel=1e-12)
        k = TomgroParameters().k
        assert entity.properties["density"] == pytest.approx(
            1 - math.exp(-k * on_its_ground), rel=1e-12
        )
    scene = initial_scene(grown.catalogue, "tomgro_box")
    assert not [entity for entity in scene.entities if "plant_id" in entity.properties]
    light = plants_light(grown, RUN, time_s=DAY_S / 2)
    assert light.par_umol_m2_s == {} and light.daily_light_integral_mol_m2_d == {}


def test_it_takes_no_crop_actions_and_no_crop_work(grown: Simulator) -> None:
    assert crop_model_refusal(CONFIG, ActionKind.HARVEST) == (
        "tomgro_box grows its crop with the reduced_tomgro model, which takes no harvest"
    )
    assert plant_ids(CONFIG) == []
    # Refused when it is read, rather than whenever its crop is asked for.
    with pytest.raises(ValidationError, match="grown by area, which takes no crop work"):
        ScenarioConfig.model_validate(
            CONFIG.model_dump()
            | {"greenhouse_id": "worked_tomgro_box", "crop_work": {"harvest_every_days": 7}}
        )


def test_its_canopy_stands_under_the_eaves() -> None:
    # Its light is read at the canopy's top: 0.675 m of planting and 4 m.
    with pytest.raises(
        ValidationError, match=re.escape("its canopy's top, 4.675 m, stands above the eaves, 4 m")
    ):
        ScenarioConfig.model_validate(
            CONFIG.model_dump() | {"crop": {"kind": "reduced_tomgro", "canopy_height_m": 4.0}}
        )


@pytest.mark.parametrize(
    ("day", "changed", "refused"),
    [
        (2, {"hours": 1}, "a crop's step of its model is 24 hours, each lived so"),
        (2, {"lai": -1.0}, "row_1's nodes or leaf area index are negative"),
        (0, {"lai": 3.0}, "row_1's canopy is not as the model plants it"),
    ],
)
def test_an_uploaded_checkpoint_no_run_reaches_is_refused(
    day: int, changed: dict[str, float], refused: str
) -> None:
    with _simulator() as simulator:
        saved = checkpoints.save_checkpoint(simulator, RUN, time_s=day * DAY_S)
        document = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
    state = document["models"]["crop"]["state"]
    if "hours" in changed:
        first = state["lived"][0]["row_1"]
        first["hours"] = first["hours"][: int(changed["hours"])]
    else:
        state["instances"][0]["state"]["lai"] = changed["lai"]

    with _simulator() as simulator, pytest.raises(InvalidRequest, match=re.escape(refused)):
        checkpoints.upload_checkpoint(simulator, document)


def test_its_records_and_its_truth_name_no_plant(grown: Simulator) -> None:
    start = run_start(grown.catalogue, "tomgro_box")
    _, run_id = air_through_a_run(grown, RUN)

    assert crop_records(grown, RUN, 2, start, run_id) == ([], [])
    truth = ground_truth(grown, RUN, until_s=3 * DAY_S)
    assert truth.readings and all(reading.plant_id is None for reading in truth.readings)


def test_a_checkpoint_keeps_its_instances_and_a_run_carries_on_from_them() -> None:
    with _simulator() as simulator:
        saved = checkpoints.save_checkpoint(simulator, RUN, time_s=2 * DAY_S)
        document = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
        crop = scenario_crop(simulator, RUN)
        assert not of_plants(crop)
        later = crop.instances_on(4)
    kept = checkpoints.read_checkpoint(document)

    assert isinstance(kept.crop, AreaCropState) and type(kept.crop) is TomgroCropState
    assert kept.crop.named == ROWS and saved.plants == 0
    assert document["models"]["crop"]["model"] == "reduced_tomgro"
    with _simulator() as simulator:
        checkpoints.upload_checkpoint(simulator, document)
        restored = scenario_crop(simulator, RUN)
        assert not of_plants(restored)
        assert list(restored.instances_on(2)) == kept.crop.instances
        assert restored.instances_on(4) == later
        # Taken over, not worked out again.
        assert restored.lived_on(1) == kept.crop.lived[1]
