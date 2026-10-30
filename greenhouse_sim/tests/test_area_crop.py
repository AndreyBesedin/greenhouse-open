"""A run's crop grown by area (P14.9, decision 0062).

- **Every model of it keeps `AreaRung`'s rules,** as every per-plant model
  keeps `CropRung`'s (`test_crop_rungs.py`): the same canopy for the same
  state and course, the state it is given left as it was, the same growth
  per m² on any scope, and states that survive a JSON round trip. The
  published models join `AREA_RUNGS` as they are registered (P14.10);
  until then, a canopy of the test's own holds the rules to account.
- **The run's crop of it** is its model on each row's scope, each of its
  model's steps in its course, its steps kept as every run's crop keeps
  them (decision 0064): a canopy of an hour's step meets one of a day's,
  growing alike, at every midnight.
- **The first driver profile** gives the house's air and the light above
  each scope, hour by hour, a step's hours at a time: the air every plant
  reads the day's mean of.
"""

from typing import Any, Final

import pytest
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.area_contract import AreaRung, HourDrivers, StepCourse
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.core.area_crop import AreaCrop, AreaInstance
from greenhouse_sim.core.clock import steps_a_day
from greenhouse_sim.core.drivers import HOUSE_HOURS, DriverProfile, house_hours
from greenhouse_sim.core.tomgro_crop import TomgroRung
from greenhouse_sim.domain.crop import Driver
from greenhouse_sim.domain.scopes import AreaBasis
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.solar.inside import Sunlight
from greenhouse_sim.solar.scopes import ScopeLight
from greenhouse_sim.solar.shadows import Shadows
from greenhouse_sim.units import DAY_S, HOUR_S, HOURS_A_DAY
from greenhouse_sim.world.scopes import row_scopes

UMOL_PER_MOL: Final = 1e6


class CanopyState(BaseModel):
    """A canopy of the test's own: its dry mass and its leaf area index, per
    m² of cultivated area."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dry_mass_g: float
    leaf_area_index: float


class Canopy:
    """A canopy growing a gram of dry mass for each mol of PAR above it while
    the air is warmer than 10 °C, its leaves an area a hundredth of a m² per
    gram, stepping `step_s` at a time."""

    def __init__(self, step_s: float = DAY_S) -> None:
        self._step_s = step_s

    @property
    def step_s(self) -> float:
        return self._step_s

    @property
    def state_type(self) -> type[CanopyState]:
        return CanopyState

    @property
    def basis(self) -> AreaBasis:
        return AreaBasis.CULTIVATED

    @property
    def drivers(self) -> frozenset[Driver]:
        return frozenset({Driver.AIR_TEMPERATURE, Driver.PAR_ABOVE})

    @property
    def canopy_height_m(self) -> float:
        return 1.5

    def planted(self) -> CanopyState:
        return CanopyState(dry_mass_g=10.0, leaf_area_index=0.1)

    def live_step(self, state: CanopyState, course: StepCourse) -> CanopyState:
        grown = sum(
            hour.par_above_umol_m2_s * HOUR_S / UMOL_PER_MOL
            for hour in course.hours
            if hour.temperature_c > 10.0
        )
        dry_mass = state.dry_mass_g + grown
        return CanopyState(dry_mass_g=dry_mass, leaf_area_index=dry_mass / 100.0)


AREA_RUNGS: Final[list[AreaRung[Any]]] = [
    Canopy(),
    Canopy(HOUR_S),
    TomgroRung(TomgroParameters(), 2.0),
]


def course(
    par: float, temperature_c: float = 20.0, hours: range = range(HOURS_A_DAY)
) -> StepCourse:
    """The `hours` of a day lit by `par` from 6 to 18 o'clock, at
    `temperature_c`: all of it by default."""
    return StepCourse(
        hours=tuple(
            HourDrivers(
                temperature_c=temperature_c,
                par_above_umol_m2_s=par if 6 <= hour < 18 else 0.0,
                co2_ppm=420.0,
            )
            for hour in hours
        )
    )


def _step_course(rung: AreaRung[Any], par: float, step: int = 0) -> StepCourse:
    """The course of a rung's step `step` of a day lit by `par`, as many
    hours as its step holds."""
    hours = round(rung.step_s / HOUR_S)
    return course(par, hours=range(step * hours, (step + 1) * hours))


def _name(rung: AreaRung[Any]) -> str:
    return f"{type(rung).__name__}-{rung.step_s:g}s"


@pytest.mark.parametrize("rung", AREA_RUNGS, ids=_name)
def test_each_area_rung_grows_the_same_for_the_same_state_and_course(rung: AreaRung[Any]) -> None:
    planted = rung.planted()
    # The step that holds noon, lit whatever its length.
    noon = int(DAY_S / 2 // rung.step_s)
    first = rung.live_step(planted, _step_course(rung, 400.0, noon))

    assert rung.live_step(planted, _step_course(rung, 400.0, noon)) == first
    assert planted == rung.planted()
    assert first != planted
    assert rung.live_step(planted, _step_course(rung, 800.0, noon)) != first


@pytest.mark.parametrize("rung", AREA_RUNGS, ids=_name)
def test_each_area_rungs_states_survive_a_json_round_trip(rung: AreaRung[Any]) -> None:
    state = rung.planted()
    for step in range(steps_a_day(rung.step_s)):
        state = rung.live_step(state, _step_course(rung, 400.0, step))

    assert rung.state_type.model_validate_json(state.model_dump_json()) == state


@pytest.mark.parametrize("rung", AREA_RUNGS, ids=_name)
def test_each_area_rung_is_driven_through_the_house_hours(rung: AreaRung[Any]) -> None:
    """The first driver profile gives every driver it declares, a step's
    hours at a time, and its step divides a day."""
    assert HOUSE_HOURS.refusal(rung.drivers) is None
    assert HOUSE_HOURS.step_refusal(rung.step_s) is None
    assert steps_a_day(rung.step_s) >= 1
    assert rung.canopy_height_m > 0.0
    assert rung.basis in set(AreaBasis)


CONFIG: Final = SCENARIO_REGISTRY["reference_greenhouse"]
SCOPES: Final = row_scopes(CONFIG.layout, CONFIG.envelope)
DAYS: Final = 6


def _crop(
    courses: dict[str, StepCourse] | None = None, step_s: float = DAY_S
) -> AreaCrop[CanopyState]:
    """The test's canopy, of a step of `step_s`, on each of the reference
    greenhouse's rows: every day each row's course as `courses` gives it, or
    a bright day for all, a step's hours of it at a time."""
    every = courses or dict.fromkeys((scope.scope_id for scope in SCOPES), course(400.0))
    hours, a_day = round(step_s / HOUR_S), steps_a_day(step_s)

    def of_step(step: int) -> dict[str, StepCourse]:
        first = step % a_day * hours
        return {
            scope_id: StepCourse(hours=day.hours[first : first + hours])
            for scope_id, day in every.items()
        }

    return AreaCrop(SCOPES, rung=Canopy(step_s), courses=of_step, days=DAYS)


def test_each_row_is_an_instance_that_lives_its_days_in_its_course() -> None:
    bright, dim = course(800.0), course(200.0)
    courses = {scope.scope_id: bright if scope.row % 2 else dim for scope in SCOPES}
    crop = _crop(courses)
    rung = Canopy()

    instances = crop.instances_on(3)
    assert [instance.scope_id for instance in instances] == [scope.scope_id for scope in SCOPES]
    for instance in instances:
        expected = rung.planted()
        for _ in range(3):
            expected = rung.live_step(expected, courses[instance.scope_id])
        assert instance.state == expected
    assert crop.course(SCOPES[0].scope_id, 2) == bright
    with pytest.raises(LookupError, match="no scope 'row_9'"):
        crop.course("row_9", 0)


def test_a_canopy_of_an_hours_step_meets_one_of_a_days_at_every_midnight() -> None:
    """Decision 0064: the same canopy, stepping an hour at a time through
    the same hours, is at each midnight the canopy that lived the day at
    once, its hourly sums added in another order."""
    hourly, daily = _crop(step_s=HOUR_S), _crop()

    assert hourly.steps == DAYS * HOURS_A_DAY
    for day in range(DAYS + 1):
        for by_hour, by_day in zip(hourly.instances_on(day), daily.instances_on(day), strict=True):
            assert by_hour.state.dry_mass_g == pytest.approx(by_day.state.dry_mass_g, rel=1e-12)
    # Between midnights, it has lived the hours ended: none lit before 6.
    assert hourly.on(6) == hourly.on(0)
    assert hourly.on(7)[0].state.dry_mass_g > hourly.on(6)[0].state.dry_mass_g
    assert hourly.course(SCOPES[0].scope_id, 30) == course(400.0, hours=range(6, 7))


def test_a_canopy_of_an_hours_step_is_as_the_hours_ended_have_it() -> None:
    """P16's QA, its fourth point: asked for at 09:00, 09:30, 10:00, 09:00
    again and 10:00 again, the canopy is each time as 9, 9, 10, 9 and 10 of
    the day's hours have it, and at the run's end as a canopy nobody asked
    about."""
    asked = _crop(step_s=HOUR_S)
    moments = [9 * HOUR_S, 9.5 * HOUR_S, 10 * HOUR_S, 9 * HOUR_S, 10 * HOUR_S]

    seen = [asked.at(moment) for moment in moments]

    nobody = _crop(step_s=HOUR_S)
    assert seen == [nobody.on(9), nobody.on(9), nobody.on(10), nobody.on(9), nobody.on(10)]
    assert seen[0] != seen[2]
    assert asked.at(DAYS * DAY_S) == _crop(step_s=HOUR_S).at(DAYS * DAY_S)


def test_two_rows_in_one_course_grow_the_same_per_m2() -> None:
    """Whatever their areas, as an area model grows per m² of its basis."""
    instances = _crop().instances_on(DAYS)

    assert len({instance.state for instance in instances}) == 1


def test_a_crop_grown_by_area_carries_on_from_its_instances_read_back() -> None:
    source = _crop()
    written = [instance.model_dump_json() for instance in source.instances_on(4)]
    read = [AreaInstance[CanopyState].model_validate_json(text) for text in written]
    seeded = _crop()
    seeded.seed(4, read, [source.lived_on(day) for day in range(4)])

    assert seeded.instances_on(DAYS) == source.instances_on(DAYS)
    with pytest.raises(ValueError, match="a crop of CanopyState canopies takes no others"):
        _crop().seed(0, list(reversed(source.instances_on(0))), [])
    with pytest.raises(ValueError, match="takes none of the run's crop actions"):
        source.growth.next_step(0, source.instances_on(0), source.lived_on(0), [object()])  # type: ignore[list-item]


def test_the_house_hours_give_each_driver_or_say_what_stands_for_it() -> None:
    assert HOUSE_HOURS.refusal(frozenset(Driver)) is None
    assert HOUSE_HOURS.substitutes(frozenset(Driver)) == {
        Driver.CANOPY_TEMPERATURE: Driver.AIR_TEMPERATURE
    }
    dark = DriverProfile("dark", 1, {Driver.AIR_TEMPERATURE: Driver.AIR_TEMPERATURE}, HOUR_S)
    assert dark.refusal(frozenset({Driver.PAR_ABOVE, Driver.CO2})) == (
        "the dark drivers give no co2_ppm, par_above_umol_m2_s"
    )


@pytest.mark.parametrize("step_s", [HOUR_S / 2, 1.5 * HOUR_S, 0.0])
def test_the_house_hours_refuse_a_step_that_is_not_a_whole_number_of_hours(step_s: float) -> None:
    """Decision 0064: a model whose step is shorter than its profile's
    resolution, or not a whole number of it, is refused, naming both."""
    refusal = HOUSE_HOURS.step_refusal(step_s)

    assert refusal == (
        f"the house_hours drivers come 3600 s at a time, and a step of {step_s:g} s "
        "is not a whole number of them"
    )


def test_the_house_hours_are_the_air_each_plant_reads_the_day_of(simulator: Simulator) -> None:
    """Hour by hour, the same air every plant reads the day's mean of, and
    the light above each scope adding up to its day's integral."""
    _, climate = climate_run(simulator, RunRequest(CONFIG.greenhouse_id))
    sunlight = Sunlight(
        CONFIG.site,
        CONFIG.run_weather(),
        air_grid(CONFIG),
        CONFIG.envelope,
        Shadows.of(CONFIG.envelope, CONFIG.layout, []),
    )
    light = ScopeLight(sunlight, SCOPES, Canopy().canopy_height_m)
    courses = house_hours(climate.house.mean_between, light, step_s=DAY_S)(1)
    day = climate.house.mean_between(DAY_S, 2 * DAY_S)
    # A quarter of a day's step: day 1's fourth, its hours 6 to 11.
    quarters = house_hours(climate.house.mean_between, light, step_s=6 * HOUR_S)(5)
    for scope_id, each in quarters.items():
        assert each.hours == courses[scope_id].hours[6:12]
    with pytest.raises(ValueError, match="is not a whole number of them"):
        house_hours(climate.house.mean_between, light, step_s=HOUR_S / 2)
    with pytest.raises(ValueError, match="a crop's step divides a day"):
        house_hours(climate.house.mean_between, light, step_s=5 * HOUR_S)

    assert set(courses) == {scope.scope_id for scope in SCOPES}
    for scope_id, each in courses.items():
        hours = each.hours
        # Each hour its own mean, the air changing through the day.
        afternoon = climate.house.mean_between(DAY_S + 13 * HOUR_S, DAY_S + 14 * HOUR_S)
        assert hours[13].temperature_c == afternoon.temperature_c
        assert len({hour.temperature_c for hour in hours}) > 1
        assert sum(hour.temperature_c for hour in hours) / len(hours) == pytest.approx(
            day.temperature_c, rel=1e-9
        )
        assert sum(hour.co2_ppm for hour in hours) / len(hours) == pytest.approx(
            day.co2_ppm, rel=1e-9
        )
        assert sum(
            hour.par_above_umol_m2_s for hour in hours
        ) * HOUR_S / UMOL_PER_MOL == pytest.approx(
            light.daily_light_integral(1)[scope_id], rel=1e-12
        )
