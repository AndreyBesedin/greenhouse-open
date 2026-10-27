"""The house's air by the whole house alone (P14.6): a scenario whose house
air's model is `whole_house` has the same house's air as the grid's, draws
it the same in every cell, samples it as the grid's sensors do after their
first two hours, and works out no air cell by cell."""

from collections.abc import Iterator
from urllib.parse import parse_qs

import numpy as np
import pytest

from greenhouse_sim.api.routes.runs import run_request
from greenhouse_sim.climate.control import CirculationLoop, Control, VentingLoop, VentStage
from greenhouse_sim.climate.day import FROM_THE_START_S, WholeHouseDay
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.settings import WholeHouseAir
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.registry import models_run
from greenhouse_sim.services.climate_readings import climate_probes
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.weather.sources import ConstantWeather

SCENARIO = "climate_box"
# Its heater on, then its fan, so that its air changes through the day.
RUN = run_request(SCENARIO, parse_qs("set=heater:1&schedule=7200:fan:1"))
GRID = SCENARIO_REGISTRY[SCENARIO]
WHOLE = GRID.model_copy(
    update={
        "climate": WholeHouseAir.model_validate(
            GRID.climate.model_dump(exclude={"kind", "mixing_m2_s"})
        )
    }
)
FIELD = f"{SCENARIO}_climate"
# Moments through its first two hours and after them.
MOMENTS_S = (0.0, 0.5 * HOUR_S, 1.5 * HOUR_S, 2.0 * HOUR_S, 5.3 * HOUR_S, 1.2 * DAY_S)


@pytest.fixture
def whole() -> Iterator[Simulator]:
    with Simulator(Catalogue(PACKAGED.with_config(WHOLE))) as simulator:
        yield simulator


def test_its_whole_house_runs_on_the_grids_settings() -> None:
    assert WHOLE.climate.kind == "whole_house"
    assert WHOLE.climate.run_settings() == GRID.climate.run_settings()
    assert models_run(WHOLE)[Part.HOUSE_AIR].model == "whole_house"


def test_its_houses_air_is_the_grids_and_is_drawn_the_same_in_every_cell(
    simulator: Simulator, whole: Simulator
) -> None:
    _, grid = climate_run(simulator, RUN)
    _, day = climate_run(whole, RUN)

    assert isinstance(day, WholeHouseDay)
    for time_s in MOMENTS_S:
        house = day.house.air_at(time_s)
        assert house == grid.house.air_at(time_s)
        field = day.field(FIELD, time_s)
        assert np.all(field.channels[AirQuantity.TEMPERATURE] == house.temperature_c)
        assert np.ptp(field.channels[AirQuantity.HUMIDITY]) == 0.0
        # In the flow its equipment makes then, as the grid's sensors sample
        # it after their first two hours.
        if time_s >= FROM_THE_START_S:
            theirs = grid.sampled(FIELD, time_s).channels
            assert all(np.array_equal(field.channels[each], theirs[each]) for each in theirs)


def test_its_sensors_sample_the_air_the_grids_sample_after_their_first_two_hours(
    simulator: Simulator, whole: Simulator
) -> None:
    grid_air, grid_id = air_through_a_run(simulator, RUN)
    whole_air, whole_id = air_through_a_run(whole, RUN)

    assert whole_id != grid_id
    for time_s in MOMENTS_S:
        sampled = whole_air(time_s).channels
        theirs = grid_air(time_s).channels
        same = all(np.array_equal(sampled[each], theirs[each]) for each in sampled)
        # Both start from the same air, the same in every cell.
        assert same == (time_s == 0.0 or time_s >= FROM_THE_START_S)


def test_it_works_out_no_air_cell_by_cell(
    whole: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its field, its sensors, its glazing, its doors and vents and its
    probes all read the whole house's air: none steps a grid run."""

    def stepped(*_: object) -> None:
        raise AssertionError("a grid run was stepped")

    monkeypatch.setattr(ClimateRun, "air_at", stepped)
    monkeypatch.setattr(ClimateRun, "started_at", stepped)
    _, day = climate_run(whole, RUN)
    time_s = 5.3 * HOUR_S

    house = day.house.air_at(time_s)
    day.field(FIELD, time_s)
    day.sampled(FIELD, time_s)
    glazing = day.glazing_at(time_s)
    day.openings_at(time_s)
    probes = climate_probes(whole, RUN, [(1.0, 1.0, 1.0)], until_s=time_s)

    assert glazing.surfaces
    assert probes.probes[0].controlled.temperature_c[-1] == pytest.approx(house.temperature_c)


def test_its_vents_and_fans_are_as_its_house_decides_them_without_a_grid_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A venting loop's vents and its fans stand as the whole house decides
    them (P11.2), in its doors' and vents' flows and its levels, with no grid
    run stepped."""
    venting = VentingLoop(
        vents=["roof_vent", "side_vent"],
        day_c=19.0,
        night_c=19.0,
        stages=[VentStage(above_c=0.0, level=0.2), VentStage(above_c=1.5, level=1.0)],
    )
    vented = WHOLE.model_copy(
        update={
            "weather": ConstantWeather(air_temperature_c=12.0),
            "control": Control(venting=venting, circulation=CirculationLoop(fans=["fan"])),
        }
    )

    def stepped(*_: object) -> None:
        raise AssertionError("a grid run was stepped")

    monkeypatch.setattr(ClimateRun, "air_at", stepped)
    monkeypatch.setattr(ClimateRun, "started_at", stepped)
    with Simulator(Catalogue(PACKAGED.with_config(vented))) as simulator:
        _, day = climate_run(simulator, run_request(SCENARIO, parse_qs("set=heater:1")))
        moment = next(
            minute * 60.0
            for minute in range(1, 4 * 60)
            if day.house.controlled_at(minute * 60.0)["roof_vent"] > 0
        )
        decided = day.house.controlled_at(moment)
        passing = {flow.opening_id for flow in day.openings_at(moment).openings}

        assert {"roof_vent", "side_vent"} <= passing
        assert day.run.levels_at(moment)["fan"] == decided["fan"] == 1.0
        day.field(FIELD, moment)
