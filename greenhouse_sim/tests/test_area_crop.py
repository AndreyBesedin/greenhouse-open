"""A run's crop grown by area (P14.9, decision 0062).

- **Every model of it keeps `AreaRung`'s rules,** as every per-plant model
  keeps `CropRung`'s (`test_crop_rungs.py`): the same canopy for the same
  state and course, the state it is given left as it was, the same growth
  per m² on any scope, and states that survive a JSON round trip. The
  published models join `AREA_RUNGS` as they are registered (P14.10);
  until then, a canopy of the test's own holds the rules to account.
- **The run's crop of it** is its model on each row's scope, each day in
  its course, its days kept as every run's crop keeps them.
- **The first driver profile** gives the house's air and the light above
  each scope, hour by hour: the air every plant reads the day's mean of.
"""

from typing import Any, Final

import pytest
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.area_contract import AreaRung, DayCourse, HourDrivers
from greenhouse_sim.core.area_crop import AreaCrop, AreaInstance
from greenhouse_sim.core.drivers import HOUSE_HOURS, DriverProfile, house_hours
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
    gram."""

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

    def live_day(self, state: CanopyState, course: DayCourse) -> CanopyState:
        grown = sum(
            hour.par_above_umol_m2_s * HOUR_S / UMOL_PER_MOL
            for hour in course.hours
            if hour.temperature_c > 10.0
        )
        dry_mass = state.dry_mass_g + grown
        return CanopyState(dry_mass_g=dry_mass, leaf_area_index=dry_mass / 100.0)


AREA_RUNGS: Final[list[AreaRung[Any]]] = [Canopy()]


def course(par: float, temperature_c: float = 20.0) -> DayCourse:
    """A day lit by `par` from 6 to 18 o'clock, at `temperature_c`."""
    return DayCourse(
        hours=tuple(
            HourDrivers(
                temperature_c=temperature_c,
                par_above_umol_m2_s=par if 6 <= hour < 18 else 0.0,
                co2_ppm=420.0,
            )
            for hour in range(HOURS_A_DAY)
        )
    )


def _name(rung: AreaRung[Any]) -> str:
    return type(rung).__name__


@pytest.mark.parametrize("rung", AREA_RUNGS, ids=_name)
def test_each_area_rung_grows_the_same_for_the_same_state_and_course(rung: AreaRung[Any]) -> None:
    planted = rung.planted()
    first = rung.live_day(planted, course(400.0))

    assert rung.live_day(planted, course(400.0)) == first
    assert planted == rung.planted()
    assert first != planted
    assert rung.live_day(planted, course(800.0)) != first


@pytest.mark.parametrize("rung", AREA_RUNGS, ids=_name)
def test_each_area_rungs_states_survive_a_json_round_trip(rung: AreaRung[Any]) -> None:
    state = rung.planted()
    for _ in range(5):
        state = rung.live_day(state, course(400.0))

    assert rung.state_type.model_validate_json(state.model_dump_json()) == state


@pytest.mark.parametrize("rung", AREA_RUNGS, ids=_name)
def test_each_area_rung_is_driven_through_the_house_hours(rung: AreaRung[Any]) -> None:
    """The first driver profile gives every driver it declares."""
    assert HOUSE_HOURS.refusal(rung.drivers) is None
    assert rung.canopy_height_m > 0.0
    assert rung.basis in set(AreaBasis)


CONFIG: Final = SCENARIO_REGISTRY["reference_greenhouse"]
SCOPES: Final = row_scopes(CONFIG.layout, CONFIG.envelope)
DAYS: Final = 6


def _crop(courses: dict[str, DayCourse] | None = None) -> AreaCrop[CanopyState]:
    """The test's canopy on each of the reference greenhouse's rows, every
    day each row's course as `courses` gives it, or a bright day for all."""
    every = courses or dict.fromkeys((scope.scope_id for scope in SCOPES), course(400.0))
    return AreaCrop(SCOPES, rung=Canopy(), courses=lambda _: every, days=DAYS)


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
            expected = rung.live_day(expected, courses[instance.scope_id])
        assert instance.state == expected
    assert crop.course(SCOPES[0].scope_id, 2) == bright
    with pytest.raises(LookupError, match="no scope 'row_9'"):
        crop.course("row_9", 0)


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
        source.growth.next_day(0, source.instances_on(0), source.lived_on(0), [object()])  # type: ignore[list-item]


def test_the_house_hours_give_each_driver_or_say_what_stands_for_it() -> None:
    assert HOUSE_HOURS.refusal(frozenset(Driver)) is None
    assert HOUSE_HOURS.substitutes(frozenset(Driver)) == {
        Driver.CANOPY_TEMPERATURE: Driver.AIR_TEMPERATURE
    }
    dark = DriverProfile("dark", 1, {Driver.AIR_TEMPERATURE: Driver.AIR_TEMPERATURE})
    assert dark.refusal(frozenset({Driver.PAR_ABOVE, Driver.CO2})) == (
        "the dark drivers give no co2_ppm, par_above_umol_m2_s"
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
    courses = house_hours(climate.house.mean_between, light)(1)
    day = climate.house.mean_between(DAY_S, 2 * DAY_S)

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
