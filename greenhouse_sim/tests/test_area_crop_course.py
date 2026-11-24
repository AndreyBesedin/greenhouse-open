"""A run's crop grown by area through its days, as a viewer charts it
(decision 0083): on each day ended by a moment, each row's state at the
day's start as its model reads it, and the house's, the rows' mean
weighted by their areas on the model's basis; refused, as its crop is, for a
moment outside the run, and for a crop grown plant by plant.
"""

import sys
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.scopes import AreaBasis
from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.area_crop import (
    AreaCropCourse,
    ScopeCourse,
    area_crop_course,
    house_course,
)
from greenhouse_sim.services.crop import of_plants, scenario_crop
from greenhouse_sim.services.crop_models import registration
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut

# The climate box, its rows growing Reduced-State TOMGRO, its air the whole
# house's: long enough for one course to be the start of another.
TOMGRO: Final = cut(
    "climate_box",
    days=10,
    sensors=("temperature_front",),
    greenhouse_id="tomgro_course_box",
    crop_model="reduced_tomgro",
    crop={"kind": "reduced_tomgro"},
)
# And growing Vanthoor's model, at an hour's step.
VANTHOOR: Final = cut(
    "climate_box",
    days=3,
    sensors=("temperature_front",),
    greenhouse_id="vanthoor_course_box",
    crop_model="vanthoor_katzin",
    crop={"kind": "vanthoor_katzin"},
)
AREA_CROPS: Final = (TOMGRO, VANTHOOR)


def _simulator() -> Simulator:
    """A simulator that knows both scenarios."""
    simulator = Simulator(Catalogue())
    for config in AREA_CROPS:
        simulator.catalogue.register(config)
    return simulator


@pytest.fixture(scope="module")
def grown() -> Iterator[Simulator]:
    with _simulator() as simulator:
        yield simulator


def _run(config: ScenarioConfig) -> RunRequest:
    return RunRequest(config.greenhouse_id)


@pytest.mark.parametrize("config", AREA_CROPS, ids=lambda config: config.crop_model)
def test_its_first_day_is_each_row_as_its_model_plants_it(
    grown: Simulator, config: ScenarioConfig
) -> None:
    area = registration(config).area
    assert area is not None
    planted = area.read(area.rung(config).planted(), config)

    course = area_crop_course(grown, _run(config), time_s=0.0)

    assert (course.time_s, course.days) == (0.0, [0])
    assert (course.model, course.basis) == (config.crop_model.value, AreaBasis.FLOOR)
    assert course.model_name == registration(config).title
    assert course.quantities == list(area.charted)
    assert course.scopes
    for scope in course.scopes:
        assert scope.values == {key: [value] for key, value in planted.items()}
    # The house's, its rows' mean, as its rows are: to the last bits that
    # weighting them gives.
    assert list(course.house) == list(planted)
    for key, value in planted.items():
        assert course.house[key] == pytest.approx([value], rel=1e-12)


@pytest.mark.parametrize("config", AREA_CROPS, ids=lambda config: config.crop_model)
def test_each_day_is_each_row_as_the_run_grows_it_by_then(
    grown: Simulator, config: ScenarioConfig
) -> None:
    """Each day's values are the crop's at the day's start, and the moment's
    day is the last: a moment within a day charts the day's start, as its
    crop is drawn."""
    area = registration(config).area
    assert area is not None
    last = config.duration_days - 1

    course = area_crop_course(grown, _run(config), time_s=(last + 0.5) * DAY_S)

    crop = scenario_crop(grown, _run(config))
    assert not of_plants(crop)
    assert course.days == list(range(last + 1))
    for day in course.days:
        for scope, instance in zip(course.scopes, crop.instances_on(day), strict=True):
            assert scope.scope_id == instance.scope_id
            read = area.read(instance.state, config)
            assert {key: values[day] for key, values in scope.values.items()} == read
    # Its rows' areas are those of its basis, the floor, and add up to the
    # house's.
    assert [scope.area_m2 for scope in course.scopes] == [scope.floor_m2 for scope in crop.scopes]
    assert sum(scope.area_m2 for scope in course.scopes) == pytest.approx(
        config.envelope.length * config.envelope.width
    )
    # Its first day's values are not its last: the crop grew between.
    assert course.house != {key: values[:1] * len(values) for key, values in course.house.items()}


def test_a_shorter_course_is_the_start_of_a_longer_one_whatever_was_asked_before() -> None:
    run = _run(TOMGRO)
    with _simulator() as simulator:
        longer = area_crop_course(simulator, run, time_s=10 * DAY_S)
        after = area_crop_course(simulator, run, time_s=5 * DAY_S)
    with _simulator() as simulator:
        first = area_crop_course(simulator, run, time_s=5 * DAY_S)

    assert after == first
    assert first.days == longer.days[:6] == [0, 1, 2, 3, 4, 5]
    for short, long in zip(first.scopes, longer.scopes, strict=True):
        assert short.values == {key: values[:6] for key, values in long.values.items()}
    assert first.house == {key: values[:6] for key, values in longer.house.items()}


def test_the_house_is_its_rows_mean_weighted_by_their_areas() -> None:
    small = ScopeCourse(scope_id="row_1", area_m2=1.0, values={"lai": [2.0, 4.0]})
    large = ScopeCourse(scope_id="row_2", area_m2=3.0, values={"lai": [10.0, 0.0]})

    # Not their plain mean, 6 and 2.
    assert house_course([small, large], "lai") == [8.0, 1.0]
    assert house_course([large], "lai") == [10.0, 0.0]


def test_its_house_is_its_rows_by_their_areas(grown: Simulator) -> None:
    course = area_crop_course(grown, _run(VANTHOOR), time_s=2 * DAY_S)
    whole = sum(scope.area_m2 for scope in course.scopes)

    for quantity in course.quantities:
        for day in course.days:
            weighted = sum(
                scope.values[quantity.key][day] * scope.area_m2 for scope in course.scopes
            )
            assert course.house[quantity.key][day] == pytest.approx(weighted / whole, rel=1e-12)


def test_a_crop_grown_plant_by_plant_is_not_found(simulator: Simulator) -> None:
    with pytest.raises(NotFound) as refused:
        area_crop_course(simulator, RunRequest("climate_box"), time_s=DAY_S)

    assert refused.value.message == (
        "climate_box grows its crop plant by plant, with the simple model, not by area"
    )


def test_a_moment_outside_the_run_is_refused(grown: Simulator) -> None:
    for outside in (-1.0, (TOMGRO.duration_days + 1) * DAY_S):
        with pytest.raises(InvalidRequest):
            area_crop_course(grown, _run(TOMGRO), time_s=outside)


def test_its_route_serves_the_course_and_refuses_as_its_crop_is(grown: Simulator) -> None:
    path = "/api/scenarios/tomgro_course_box/area_crop"
    served = respond(grown, "GET", f"{path}?t={2.5 * DAY_S}")

    assert served.status == HTTPStatus.OK
    assert AreaCropCourse.model_validate(served.body) == area_crop_course(
        grown, _run(TOMGRO), time_s=2.5 * DAY_S
    )
    assert respond(grown, "GET", path).status == HTTPStatus.OK
    assert respond(grown, "GET", f"{path}?t=-5").status == HTTPStatus.BAD_REQUEST
    assert respond(grown, "GET", f"{path}?t=noon").status == HTTPStatus.BAD_REQUEST
    assert respond(grown, "GET", f"{path}?set=no_such_heater:1").status == HTTPStatus.BAD_REQUEST
    elsewhere = respond(grown, "GET", "/api/scenarios/no_such_scenario/area_crop")
    assert elsewhere.status == HTTPStatus.NOT_FOUND
    by_plant = respond(grown, "GET", "/api/scenarios/climate_box/area_crop")
    assert by_plant.status == HTTPStatus.NOT_FOUND
