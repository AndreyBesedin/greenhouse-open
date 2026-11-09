"""A scenario whose rows grow Vanthoor's model as Katzin simplified it, run
(decisions 0060 and 0062, milestone B): the services grow it by area, on
each row's scope, an hour at a time, in the house's air and the light above
each row; keep it in a checkpoint and carry on from it; replay it as they
replay any run; and take no crop work or crop action on it. What the rung
does on its own, against its reproduction, is `test_vanthoor.py`'s.
"""

import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind
from pydantic import ValidationError

from greenhouse_sim.biology.tomato.vanthoor.parameters import INITIAL_STATE
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scene.snapshot import SceneEntityKind
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.crop import crop_scene, of_plants, scenario_crop
from greenhouse_sim.services.crop_models import VanthoorCropState, registration
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.replay import day_probes
from greenhouse_sim.services.runs import RunRequest, crop_model_refusal
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S, HOURS_A_DAY
from greenhouse_sim.world.scopes import row_scopes

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut

# The climate box, its rows growing Vanthoor's model, its air the whole
# house's; one sensor, to keep its run short.
CONFIG: Final = cut(
    "climate_box",
    days=3,
    sensors=("temperature_front",),
    greenhouse_id="vanthoor_box",
    crop_model="vanthoor_katzin",
    crop={"kind": "vanthoor_katzin"},
)
RUN: Final = RunRequest("vanthoor_box")
# Its heater, to give a run other air than another.
HEATED: Final = RunRequest("vanthoor_box", levels={"heater": 1.0})
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


def test_its_run_grows_its_crop_by_area_an_hour_at_a_time(grown: Simulator) -> None:
    crop = scenario_crop(grown, RUN)
    assert not of_plants(crop)
    area = registration(CONFIG).area
    assert area is not None
    rung = area.rung(CONFIG)

    assert crop.steps_a_day == HOURS_A_DAY
    instances = crop.instances_on(2)
    assert [instance.scope_id for instance in instances] == ROWS == ["row_1", "row_2"]
    for instance in instances:
        expected, summed = INITIAL_STATE, INITIAL_STATE.t_can_sum
        for step in range(2 * HOURS_A_DAY):
            course = crop.course(instance.scope_id, step)
            assert len(course.hours) == 1
            expected = rung.live_step(expected, course)
            summed += course.hours[0].temperature_c * HOUR_S / DAY_S
        assert instance.state == expected
        # Its temperature sum is the air's hours'; in the box's polar night
        # it assimilates nothing, and its buffer is drawn on.
        assert instance.state.t_can_sum == pytest.approx(summed, rel=1e-12)
        assert instance.state.c_buf < INITIAL_STATE.c_buf


def test_its_scene_draws_each_rows_canopy_and_no_plant(grown: Simulator) -> None:
    drawn = crop_scene(grown, RUN, time_s=2 * DAY_S).entities
    crop = scenario_crop(grown, RUN)
    assert not of_plants(crop)
    instances = crop.instances_on(2)

    assert [entity.kind for entity in drawn] == [SceneEntityKind.CANOPY] * len(ROWS)
    for entity, instance in zip(drawn, instances, strict=True):
        assert entity.properties["model"] == "vanthoor_katzin"
        assert entity.properties["buffer_ch2o_mg_m2"] == instance.state.c_buf
        assert entity.properties["proxy"] is True and entity.properties["prediction"] is True


def test_it_takes_no_crop_actions_and_no_crop_work() -> None:
    assert crop_model_refusal(CONFIG, ActionKind.HARVEST) == (
        "vanthoor_box grows its crop with the vanthoor_katzin model, which takes no harvest"
    )
    assert plant_ids(CONFIG) == []
    with pytest.raises(ValidationError, match="grown by area, which takes no crop work"):
        ScenarioConfig.model_validate(
            CONFIG.model_dump()
            | {"greenhouse_id": "worked_vanthoor_box", "crop_work": {"lower_every_days": 7}}
        )


def test_its_replay_is_the_same_and_another_run_of_it_is_not() -> None:
    with _simulator() as first, _simulator() as second:
        replayed = [probe.digest for probe in day_probes(first, RUN, 2)]
        again = [probe.digest for probe in day_probes(second, RUN, 2)]
        heated = [probe.digest for probe in day_probes(second, HEATED, 2)]

    assert replayed == again
    assert not set(replayed) & set(heated)


def test_a_checkpoint_keeps_its_instances_and_a_run_carries_on_from_them() -> None:
    with _simulator() as simulator:
        saved = checkpoints.save_checkpoint(simulator, RUN, time_s=DAY_S)
        document = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
        crop = scenario_crop(simulator, RUN)
        assert not of_plants(crop)
        later = crop.instances_on(3)
    kept = checkpoints.read_checkpoint(document)

    assert type(kept.crop) is VanthoorCropState
    assert kept.crop.named == ROWS and len(kept.crop.lived) == HOURS_A_DAY
    assert document["models"]["crop"]["model"] == "vanthoor_katzin"
    assert document["models"]["crop"]["version"] == 1
    with _simulator() as simulator:
        checkpoints.upload_checkpoint(simulator, document)
        restored = scenario_crop(simulator, RUN)
        assert not of_plants(restored)
        assert list(restored.instances_on(1)) == kept.crop.instances
        assert restored.instances_on(3) == later
        # Taken over, not worked out again.
        assert restored.lived_on(5) == kept.crop.lived[5]


def test_an_uploaded_checkpoint_whose_hours_do_not_add_up_is_refused() -> None:
    with _simulator() as simulator:
        saved = checkpoints.save_checkpoint(simulator, RUN, time_s=DAY_S)
        document = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
    canopy = document["models"]["crop"]["state"]["instances"][0]["state"]
    canopy["t_can_sum"] += 1.0

    with (
        _simulator() as simulator,
        pytest.raises(InvalidRequest, match=re.escape("row_1's temperature sum is")),
    ):
        checkpoints.upload_checkpoint(simulator, document)
