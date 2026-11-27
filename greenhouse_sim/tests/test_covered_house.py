"""The house air's `vanthoor` model (P24.3, decision 0078): its air beside
its cover and the sky. Its fluxes agree with GreenLight's at the same
states; its course with scipy's BDF; at its limit it gives the whole
house's air; heat and water are conserved; a run through a checkpoint is
the run from the start; and a day costs well under a second."""

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Final

import numpy as np
import pytest
import scipy.linalg
from pydantic import ValidationError
from scipy.integrate import solve_ivp

from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.covered import CoveredHouse, envelope_volume_m3, house_nodes
from greenhouse_sim.climate.exponential import matrix_exponential
from greenhouse_sim.climate.glazing import (
    FILM_PER_WIND_W_M2K,
    STILL_FILM_W_M2K,
    inside_film_w_m2k,
)
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.psychrometrics import ATMOSPHERE_PA, WATER_PER_AIR_G_KG
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.sky import clear_sky_emissivity, sky_temperature_c
from greenhouse_sim.climate.transport import AIR_HEAT_CAPACITY_J_KG_K
from greenhouse_sim.climate.vanthoor import (
    AIR,
    CONDENSED,
    LATENT_HEAT_J_KG,
    WATER,
    Films,
    Held,
    HouseNodes,
    Layers,
)
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services import cfd, checkpoints, climate_readings
from greenhouse_sim.services.climate_runs import climate_day, climate_run
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.units import AIR_DENSITY_KG_M3
from greenhouse_sim.weather.presets import COLD_SPRING_DAY
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.materials import UNDESCRIBED_SHEET

sys.path.insert(0, str(Path(__file__).parent))
from short_runs import cut, simulator_of

FLUXES: Final = (
    Path(__file__).resolve().parents[2]
    / "research/reproductions/vanthoor_climate/reference/fluxes.json"
)
BOX: Final = SCENARIO_REGISTRY["climate_box"]
HOUR_S: Final = 3600.0
# The climate box's cover, worked out by hand: its side walls, 12 m by 4 m;
# its end walls, 6.4 m by 4 m under a gable 0.8 m high; its roof's two slopes,
# 12 m by the slope from its eaves to its ridge, 3.2 m across and 0.8 m up.
BOX_COVER_M2: Final = 2 * 12 * 4 + 2 * (6.4 * 4 + 6.4 * 0.8 / 2) + 2 * 12 * math.hypot(3.2, 0.8)
BOX_VOLUME_M3: Final = 12 * (6.4 * 4 + 6.4 * 0.8 / 2)
# How closely the model's fluxes agree with GreenLight's where it takes
# Buck's saturation pressure in place of GreenLight's: the two differ by
# 0.2 % at 6 °C, a share of a condensing cover's vapour pressure deficit.
SATURATION_SHARE: Final = 0.02
# How closely its course agrees with BDF's at a relative tolerance of 1e-10,
# over an hour of minutes: the linearisation's error, which `STRAYS_*` bound
# each piece.
BDF_C: Final = 1e-3
BDF_G_KG: Final = 1e-3
# How closely its limit gives the whole house's air, a day on: what its
# cover's little heat holds back, and the exponential's rounding.
LIMIT_C: Final = 1e-5
LIMIT_G_KG: Final = 1e-6


def _greenlights_house(given: dict[str, float]) -> tuple[HouseNodes, np.ndarray, Held]:
    """The model's nodes and state at a case of `fluxes.json`, its cover
    GreenLight's Netherlands roof (Vanthoor 2011, Table 8.2) over its area,
    and what holds then."""
    roof = Layers(
        area_m2=given["aCov"],
        conductance_w_m2k=1.05 / 4e-3,
        layer_j_m2k=0.0,
        emissivity=0.85,
        absorptance=0.02,
    )
    nodes = HouseNodes(volume_m3=given["aFlr"] * 4.0, floor_m2=given["aFlr"], layers=[roof])
    vapour = given["vpTop"]
    water = WATER_PER_AIR_G_KG * vapour / (ATMOSPHERE_PA - vapour)
    state = nodes.state(given["tTop"], water, [(given["tCovIn"], given["tCovE"])])
    held = Held(
        outside_c=given["tOut"],
        outside_g_kg=0.0,
        wind_m_s=given["wind"],
        sky_c=given["tSky"],
        sun_on_floor_w=given["iGlob"] * given["aFlr"],
    )
    return nodes, state, held


def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(FLUXES.read_text())["cases"]
    return cases


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["case"])
def test_its_fluxes_are_greenlights_at_the_same_states(case: dict[str, Any]) -> None:
    """Each per m² of floor, as GreenLight gives them; but the conduction
    through the cover, which the model takes per m² of the cover itself."""
    given, theirs = case["given"], case["fluxes"]
    nodes, state, held = _greenlights_house(given)
    ours = nodes.fluxes(state, held)
    floor, cover = given["aFlr"], given["aCov"]

    assert ours["air_cover_0_w"] / floor == pytest.approx(theirs["hTopCovIn"], rel=1e-12)
    assert ours["through_cover_0_w"] / cover == pytest.approx(theirs["hCovInCovE"], rel=1e-12)
    assert ours["cover_outside_0_w"] / floor == pytest.approx(theirs["hCovEOut"], rel=1e-12)
    assert ours["cover_sky_0_w"] / floor == pytest.approx(theirs["rCovESky"], rel=1e-12)
    assert ours["sun_cover_0_w"] / floor == pytest.approx(theirs["rGlobSunCovE"], rel=1e-12)
    condensing = ours["condensing_0_kg_s"] / floor
    assert condensing == pytest.approx(theirs["mvTopCovIn"], rel=SATURATION_SHARE, abs=1e-12)
    assert LATENT_HEAT_J_KG * condensing == pytest.approx(
        theirs["lTopCovIn"], rel=SATURATION_SHARE, abs=1e-6
    )


def test_the_sheet_it_reads_is_greenlights_roof() -> None:
    """Single glass, as the catalogue gives it, is GreenLight's roof: its
    conduction, emissivity and absorption; each of its layers holds a tenth
    of its heat, per m² of the cover rather than GreenLight's floor."""
    theirs = _cases()[0]["fluxes"]
    layers = Layers.of(UNDESCRIBED_SHEET, 1.0)

    assert layers.conductance_w_m2k == pytest.approx(theirs["hecCovInCovE"])
    assert layers.emissivity == pytest.approx(theirs["epsCovFir"])
    assert layers.absorptance == pytest.approx((theirs["aCovPar"] + theirs["aCovNir"]) / 2)
    # GreenLight's capacity is per m² of floor, a 25° roof's cos(25°) of the
    # cover's own.
    assert layers.layer_j_m2k * math.cos(math.radians(25)) == pytest.approx(theirs["capCovIn"])


def _night() -> tuple[HouseNodes, np.ndarray, Held]:
    """A small house on a cold night, heated, its cover wet."""
    nodes = HouseNodes(
        volume_m3=400.0, floor_m2=100.0, layers=[Layers.of(UNDESCRIBED_SHEET, 180.0)]
    )
    held = Held(
        outside_c=2.0,
        outside_g_kg=3.5,
        wind_m_s=3.0,
        sky_c=-12.0,
        air_heat_w=20_000.0,
        exchanged_m3_s=0.1,
    )
    return nodes, nodes.state(15.0, 9.0, [(10.0, 6.0)]), held


def test_its_course_is_bdfs_at_tight_tolerances() -> None:
    nodes, start, held = _night()
    state, condensed = start.copy(), 0.0
    for _ in range(60):
        end = nodes.course(state, held, 60.0).at(60.0)
        condensed += float(end[CONDENSED])
        state = end.copy()
        state[CONDENSED] = 0.0

    reference = solve_ivp(
        lambda _t, y: nodes.rates(y, held),
        (0.0, HOUR_S),
        start,
        method="BDF",
        rtol=1e-10,
        atol=1e-10,
    ).y[:, -1]
    assert float(state[AIR]) == pytest.approx(reference[AIR], abs=BDF_C)
    assert float(state[WATER]) == pytest.approx(reference[WATER], abs=BDF_G_KG)
    assert np.allclose(state[3:], reference[3:], atol=BDF_C)
    assert condensed == pytest.approx(reference[CONDENSED], rel=1e-3)
    # It moved: the air warms, the cover takes water.
    assert float(state[AIR]) > float(start[AIR]) + 5.0
    assert condensed > 0.1


def test_shut_off_from_the_outside_it_keeps_the_heat_it_is_given_and_its_water() -> None:
    """With no air exchanged, no outside film and no longwave, the heat the
    air and the cover gain is the heater's and the condensed water's latent
    heat, and the water the air loses is what condensed."""
    sheet = Layers.of(UNDESCRIBED_SHEET, 180.0)
    shut = Layers(
        area_m2=sheet.area_m2,
        conductance_w_m2k=sheet.conductance_w_m2k,
        layer_j_m2k=sheet.layer_j_m2k,
        emissivity=0.0,
        absorptance=0.0,
    )
    nodes = HouseNodes(
        volume_m3=400.0,
        floor_m2=100.0,
        layers=[shut],
        films=Films(still_w_m2k=0.0, per_wind=0.0),
    )
    held = Held(outside_c=2.0, outside_g_kg=0.0, wind_m_s=3.0, sky_c=-12.0, air_heat_w=5_000.0)
    start = nodes.state(15.0, 9.0, [(6.0, 5.0)])
    end = nodes.course(start, held, 60.0).at(60.0)

    air_j_k = AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K * 400.0
    layer_j_k = shut.layer_j_m2k * shut.area_m2
    gained = air_j_k * (end[AIR] - start[AIR]) + layer_j_k * (end[3] + end[4] - start[3] - start[4])
    condensed = float(end[CONDENSED])
    assert condensed > 0
    assert gained == pytest.approx(5_000.0 * 60.0 + LATENT_HEAT_J_KG * condensed, rel=1e-9)
    lost_kg = (start[WATER] - end[WATER]) * AIR_DENSITY_KG_M3 * 400.0 / 1000.0
    assert lost_kg == pytest.approx(condensed, rel=1e-9)


def _box_run(weather: object = COLD_SPRING_DAY) -> ClimateRun:
    config = BOX.model_copy(update={"weather": weather})
    return ClimateRun(
        base=config.airflow,
        equipment=config.layout.equipment,
        schedule=Schedule.from_start({"heater": 1.0}),
        settings=config.climate.run_settings(),
        grid=air_grid(config),
        solid=cfd.geometry(PACKAGED, "climate_box").solid(),
        weather=config.run_weather(),
    )


def test_at_its_limit_it_gives_the_whole_houses_air() -> None:
    """A cover of the whole house's glass, its films its U's and holding next
    to no heat, radiating nothing and wetted by nothing, over the whole
    house's glazed area and volume: the whole house's air, through a day."""
    whole = WholeHouse(_box_run())
    ((glass, per_u),) = whole._held({"heater": 1.0}).glass_m3_s_per_u
    massless = Layers(
        area_m2=per_u * AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K,
        conductance_w_m2k=1.0 / glass.sheet_m2k_w,
        layer_j_m2k=1e-2,
        emissivity=0.0,
        absorptance=0.0,
    )
    films = Films(
        inside_w_m2k=inside_film_w_m2k(glass.u_w_m2k, glass.sheet_m2k_w),
        still_w_m2k=STILL_FILM_W_M2K,
        per_wind=FILM_PER_WIND_W_M2K,
    )
    nodes = HouseNodes(
        volume_m3=whole.volume_m3, floor_m2=1.0, layers=[massless], films=films, condenses=False
    )
    covered = CoveredHouse(_box_run(), nodes)

    for moment in (HOUR_S, 6 * HOUR_S, DAY_S):
        ours, theirs = covered.air_at(moment), whole.air_at(moment)
        assert ours.temperature_c == pytest.approx(theirs.temperature_c, abs=LIMIT_C)
        assert ours.humidity_g_kg == pytest.approx(theirs.humidity_g_kg, abs=LIMIT_G_KG)
        assert ours.co2_ppm == pytest.approx(theirs.co2_ppm, rel=1e-12)
        assert ours.condensed_kg == pytest.approx(theirs.condensed_kg, abs=1e-9)
        assert ours.heated_j == theirs.heated_j


def test_a_stretch_holds_the_weathers_and_the_houses_own() -> None:
    """Its nodes are given the sun on its floor outside, the sky above the
    weather, the air its doors, vents and gaps exchange, and the heat and
    water its equipment and the sun give and take."""
    sunny = ConstantWeather(
        air_temperature_c=8.0, global_radiation_w_m2=400.0, cloud_cover_pct=30.0, wind_speed_m_s=2.0
    )
    run = _box_run(sunny)
    house = CoveredHouse(run, house_nodes(BOX.envelope, BOX.cover, run.glass))
    noon = 12 * HOUR_S
    air, steady = house.air_at(noon), house._held({"heater": 1.0})
    outside = run.weather.at(noon)

    course = house._course(air, steady, outside, noon, sun_w=1_234.0)
    held = course.nodes.held  # type: ignore[attr-defined]

    assert held.sun_on_floor_w == pytest.approx(400.0 * 12 * 6.4)
    assert held.sky_c == sky_temperature_c(outside)
    assert held.outside_c == 8.0
    assert held.wind_m_s == 2.0
    assert held.air_heat_w == steady.heat_w + 1_234.0
    assert held.drying_kg_s == steady.water_removed_kg_s
    # Its doors and vents shut, the air its gaps leak: a share of its own air.
    leaks = run.settings.infiltration_per_s(2.0) * house.volume_m3
    assert held.exchanged_m3_s == pytest.approx(leaks, rel=1e-12)


def test_its_geometry_is_the_envelopes_own() -> None:
    nodes = house_nodes(BOX.envelope, BOX.cover, _box_run().glass)

    assert envelope_volume_m3(BOX.envelope) == pytest.approx(BOX_VOLUME_M3)
    assert nodes.volume_m3 == pytest.approx(BOX_VOLUME_M3)
    assert nodes.floor_m2 == pytest.approx(12 * 6.4)
    ((layers),) = nodes.layers
    assert layers.area_m2 == pytest.approx(BOX_COVER_M2)


def _covered(scenario_id: str, greenhouse_id: str, days: int) -> ScenarioConfig:
    """A packaged scenario, its runs `days` long, its house's air the
    `vanthoor` model's, as its own air starts."""
    air = SCENARIO_REGISTRY[scenario_id].climate.model_dump(
        exclude={"kind", "mixing_m2_s", "glazing_u_w_m2k"}, exclude_unset=True
    )
    return cut(
        scenario_id,
        days=days,
        season=True,
        greenhouse_id=greenhouse_id,
        climate={"kind": "vanthoor", **air},
    )


def test_a_scenario_runs_its_air_by_it_as_its_manifest_names_it() -> None:
    config = _covered("climate_box", "covered_box", 1)
    with simulator_of(config) as simulator:
        day = climate_day(
            simulator, ("covered_box", "default", "default", (("heater", 1.0),), (), (), ())
        )
        air = day.house.air_at(HOUR_S)

    assert isinstance(day.house, CoveredHouse)
    assert air.temperature_c > config.climate.start_temperature_c


def test_a_scenario_giving_its_glazings_u_beside_it_is_refused() -> None:
    with pytest.raises(ValidationError, match="takes its glass from its cover's sheets"):
        ScenarioConfig.model_validate(
            BOX.model_dump() | {"climate": {"kind": "vanthoor", "glazing_u_w_m2k": 4.0}}
        )


@pytest.mark.slow
def test_its_air_through_a_checkpoint_is_its_air_from_the_start() -> None:
    """Its cover's layers kept beside its air, read back from the JSON a
    store keeps them in: the run restored works out nothing before the hour
    the checkpoint keeps, and its air after is the run's from the start,
    loops switching included."""
    config = _covered("reference_greenhouse", "covered_reference", 3)
    run = RunRequest("covered_reference")
    with simulator_of(config) as worker:
        made = checkpoints.make_checkpoint(worker, run, DAY_S)
    document = json.loads(made.model_dump_json())

    assert document["models"]["house_air"]["state"]["cover_c"]
    with simulator_of(config) as restored, simulator_of(config) as start:
        checkpoints.upload_checkpoint(restored, document)
        for moment in (DAY_S + 60.0, DAY_S + 4 * HOUR_S + 30.5, DAY_S + 12 * HOUR_S):
            assert climate_readings.house_air_at(
                restored, run, moment
            ) == climate_readings.house_air_at(start, run, moment)
        house = climate_run(restored, run)[1].house
        assert [m for m in house._moments if 0.0 < m < DAY_S - HOUR_S] == []


def test_a_checkpoint_of_its_air_without_its_cover_is_refused() -> None:
    config = _covered("climate_box", "covered_box", 2)
    run = RunRequest("covered_box")
    with simulator_of(config) as worker:
        document = json.loads(checkpoints.make_checkpoint(worker, run, DAY_S).model_dump_json())
    document["models"]["house_air"]["state"] = None

    with (
        simulator_of(config) as restored,
        pytest.raises(InvalidRequest, match="beside a cover of 1 glasses"),
    ):
        checkpoints.upload_checkpoint(restored, document)


def test_it_runs_a_day_in_well_under_a_second() -> None:
    house = CoveredHouse(_box_run(), house_nodes(BOX.envelope, BOX.cover, _box_run().glass))
    house.air_at(60.0)

    started = time.perf_counter()
    house.air_at(DAY_S)
    assert time.perf_counter() - started < 1.0


def test_the_sky_is_the_weathers_where_it_records_it() -> None:
    still = {"air_temperature_c": 5.0, "barometric_pressure_hpa": 1013.0}

    assert sky_temperature_c(WeatherState(**still, sky_temperature_c=-17.5)) == -17.5
    longwave = WeatherState(**still, downward_longwave_w_m2=5.67e-8 * 260.0**4)
    assert sky_temperature_c(longwave) == pytest.approx(260.0 - 273.15)


def test_else_it_is_pratas_clear_sky_under_unsworth_and_monteiths_clouds() -> None:
    # Prata (1996) by hand: e = 0.8 × 611.21 Pa at 0 °C, 4.889 68 hPa;
    # w = 46.5 e / 273.15 K = 0.832 400; ε = 1 - (1 + w) exp(-(1.2 + 3w)^½).
    assert clear_sky_emissivity(0.0, 4.88968) == pytest.approx(0.7321114, abs=1e-6)
    clear = WeatherState(
        air_temperature_c=0.0, relative_humidity_pct=80.0, barometric_pressure_hpa=1013.0
    )
    overcast = clear.model_copy(update={"cloud_cover_pct": 100.0})

    assert sky_temperature_c(clear) == pytest.approx(0.7321114**0.25 * 273.15 - 273.15, abs=1e-3)
    # Overcast, it radiates as 0.16 ε_clr + 0.84 of a black body at the air's.
    assert sky_temperature_c(overcast) == pytest.approx(
        (0.16 * 0.7321114 + 0.84) ** 0.25 * 273.15 - 273.15, abs=1e-3
    )


def test_the_exponential_is_scipys() -> None:
    generator = np.random.default_rng(7)
    for size in (2, 5, 7):
        for scale in (1e-3, 0.3, 4.0, 60.0):
            matrix = generator.normal(size=(size, size)) * scale
            # Decaying and stiff, as a house's nodes are.
            matrix -= np.diag(np.abs(generator.normal(size=size)) * scale * 3)
            expected = scipy.linalg.expm(matrix)
            assert np.allclose(matrix_exponential(matrix), expected, rtol=1e-10, atol=1e-14)
