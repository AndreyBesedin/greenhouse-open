"""A described cover gives every model its glass (decision 0080): its sheets
give `grid` and `whole_house` their glass's U, wall by wall and over the
roof, and the sunlight its transmittance; a scenario that gives the house
air's `glazing_u_w_m2k` beside it is refused, naming both; and its file
writes the cover alone."""

import copy
import json
import math
from typing import Any, Final

import numpy as np
import pytest
from pydantic import ValidationError

from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.glazing import (
    INSIDE_FILM_W_M2K,
    REFERENCE_WIND_M_S,
    WALLS,
    Glass,
    HouseGlass,
    glazed_cells,
    glazing_at,
    inside_film_w_m2k,
)
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.settings import GridAir
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.manifest_files import MANIFESTS_DIR, scenario_from_manifest
from greenhouse_sim.scenarios.scenario_files import export_scenario_file, import_scenario_file
from greenhouse_sim.services import cfd
from greenhouse_sim.services.climate_runs import climate_day
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.solar.glass import DIFFUSE_TRANSMITTANCE, NORMAL_TRANSMITTANCE, Glazing
from greenhouse_sim.solar.shadows import roof_shading
from greenhouse_sim.world.components import Cover
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.materials import COVER_MATERIALS, CoverMaterial, CoverMaterialName

# The climate box: 12 m by 6.4 m, x east and y north, its eaves 4 m up.
BOX = SCENARIO_REGISTRY["climate_box"]
SINGLE: Final = COVER_MATERIALS[CoverMaterialName.SINGLE_GLASS].properties
# A twin-wall sheet given by its properties, for a test: no source.
TWIN_WALL: Final[dict[str, Any]] = {
    "shortwave_beam_transmittance": 0.8,
    "shortwave_diffuse_transmittance": 0.7,
    "shortwave_reflectance": 0.12,
    "longwave_emissivity": 0.9,
    "longwave_transmittance": 0.03,
    "thickness_m": 0.008,
    "conductivity_w_m_k": 0.2,
    "volumetric_heat_capacity_j_m3_k": 1.4e6,
}
TWIN: Final = CoverMaterial.model_validate(TWIN_WALL)
# Single glass over the roof and three walls, the north wall twin-wall.
MIXED: Final = Cover.model_validate(
    {"roof": "single_glass", "walls": {"side_wall_left": TWIN_WALL}}
)
ALL_TWIN: Final = Cover.model_validate({"roof": TWIN_WALL})
SHUT_HOUR_S = 3600.0


def test_single_glass_described_passes_what_a_configured_six_does() -> None:
    """The inner film is the one single glass's tabulated 6 W/m²K implies,
    so the catalogue's single glass passes 6.007 W/m²K: its 4 mm at 1.05
    W/mK conducts a little more than the 1.0 a configured U's glass is
    taken at."""
    glass = Glass.of(SINGLE)

    assert INSIDE_FILM_W_M2K == pytest.approx(8.5, abs=0.01)
    assert glass.u_w_m2k == pytest.approx(6.007, abs=5e-4)
    assert glass.sheet_m2k_w == pytest.approx(0.004 / 1.05)


def test_a_sheets_u_is_its_films_and_its_conduction_in_turn() -> None:
    """Worked by hand: the inner film 1 / 8.502, the sheet 0.008 m over
    0.2 W/mK, and the outside film 1 / (5.8 + 4.1 × 4) in the reference
    wind, or 1 / 5.8 in still air."""
    glass = Glass.of(TWIN)

    assert glass.u_w_m2k == pytest.approx(1 / (1 / 8.502 + 0.04 + 1 / 22.2), rel=1e-4)
    assert glass.u_in(0.0) == pytest.approx(1 / (1 / 8.502 + 0.04 + 1 / 5.8), rel=1e-4)
    assert glass.u_in(REFERENCE_WIND_M_S) == pytest.approx(glass.u_w_m2k)


def test_a_thick_sheets_surface_lies_by_its_own_inner_film() -> None:
    glass = Glass.of(TWIN)
    u = glass.u_in(2.0)

    assert inside_film_w_m2k(glass.u_w_m2k, glass.sheet_m2k_w) == pytest.approx(INSIDE_FILM_W_M2K)
    assert glass.surface_c(20.0, 0.0, 2.0) == pytest.approx(20.0 - u / INSIDE_FILM_W_M2K * 20.0)


def test_a_cover_makes_the_roofs_slopes_of_its_sheet_and_each_wall_of_its_own() -> None:
    glass = HouseGlass.described(MIXED)

    assert glass.of("side_wall_left") == Glass.of(TWIN)
    assert all(
        glass.of(surface) == Glass.of(SINGLE)
        for surface in ("roof_1_left", "roof_1_right", "side_wall_right", "end_wall_front")
    )
    assert HouseGlass.configured(6.0).walls == dict.fromkeys(WALLS, Glass(6.0))


def test_each_wall_and_roof_slope_passes_its_own_sheets_heat() -> None:
    grid, solid = air_grid(BOX), cfd.geometry(PACKAGED, "climate_box").solid()
    glazed = glazed_cells(BOX.envelope, grid, solid)
    outside = BOX.run_weather().at(0.0)
    warmer = np.where(solid, 0.0, np.full(solid.shape, outside.air_temperature_c + 10.0))
    wind = outside.wind_speed_m_s

    glazing = glazing_at(glazed, warmer, outside, HouseGlass.described(MIXED), 0.0)

    passed = {
        surface.surface_id: surface.loss_w / (glazed[surface.surface_id].area_m2() * 10.0)
        for surface in glazing.surfaces
    }
    assert passed.pop("side_wall_left") == pytest.approx(Glass.of(TWIN).u_in(wind))
    assert passed == pytest.approx(dict.fromkeys(passed, Glass.of(SINGLE).u_in(wind)))
    assert glazing.u_w_m2k == pytest.approx(Glass.of(SINGLE).u_in(wind))


def _run(glass: HouseGlass | None = None, glazing_u_w_m2k: float = 6.0) -> ClimateRun:
    """The climate box, shut, its heater on, through its glass."""
    settings = BOX.climate.run_settings().model_copy(update={"glazing_u_w_m2k": glazing_u_w_m2k})
    return ClimateRun(
        base=BOX.airflow,
        equipment=BOX.layout.equipment,
        schedule=Schedule.from_start({"heater": 1.0}),
        settings=settings,
        grid=air_grid(BOX),
        solid=cfd.geometry(PACKAGED, "climate_box").solid(),
        weather=BOX.run_weather(),
        glass=glass,
    )


def test_a_cover_of_one_sheet_runs_as_the_u_it_gives_under_either_model() -> None:
    """Its sheet's U, configured, runs the very same air: the whole house's
    and the grid's."""
    described = _run(HouseGlass.described(ALL_TWIN))
    configured = _run(glazing_u_w_m2k=Glass.of(TWIN).u_w_m2k)

    assert WholeHouse(described).air_at(SHUT_HOUR_S) == WholeHouse(configured).air_at(SHUT_HOUR_S)
    assert np.array_equal(
        described.air_at(SHUT_HOUR_S).temperature, configured.air_at(SHUT_HOUR_S).temperature
    )


def test_a_wall_of_a_sheet_that_passes_less_keeps_the_house_warmer() -> None:
    single, mixed, twin = (
        WholeHouse(_run(HouseGlass.described(cover))).air_at(SHUT_HOUR_S).temperature_c
        for cover in (Cover(roof=CoverMaterialName.SINGLE_GLASS), MIXED, ALL_TWIN)
    )

    assert single < mixed < twin


def _towards(azimuth_deg: float, elevation_deg: float) -> Vector3:
    """The unit vector towards the sun, x east and y north."""
    azimuth, elevation = math.radians(azimuth_deg), math.radians(elevation_deg)
    return Vector3(
        x=math.sin(azimuth) * math.cos(elevation),
        y=math.cos(azimuth) * math.cos(elevation),
        z=math.sin(elevation),
    )


@pytest.mark.parametrize(
    ("point", "towards", "passed"),
    [
        # A low sun from the north, through the twin-wall north wall.
        ((6.0, 5.0, 1.0), _towards(0.0, 10.0), 0.8 / 0.85),
        # From the south, through the single glass of the south wall.
        ((6.0, 1.4, 1.0), _towards(180.0, 10.0), 1.0),
        # From high up, through the roof.
        ((6.0, 3.2, 1.0), _towards(180.0, 70.0), 1.0),
    ],
)
def test_the_beam_passes_the_sheet_of_the_surface_it_crosses(
    point: tuple[float, float, float], towards: Vector3, passed: float
) -> None:
    points = np.array([point])

    described = Glazing(BOX.envelope, MIXED).beam_transmittance(points, towards)
    single = Glazing(BOX.envelope).beam_transmittance(points, towards)

    assert single[0] > 0
    assert described[0] / single[0] == pytest.approx(passed)


def test_the_diffuse_sky_passes_the_roofs_sheet() -> None:
    assert Glazing(BOX.envelope).diffuse_transmittance == DIFFUSE_TRANSMITTANCE
    assert (
        Glazing(BOX.envelope, MIXED).diffuse_transmittance == SINGLE.shortwave_diffuse_transmittance
    )
    assert Glazing(BOX.envelope, ALL_TWIN).diffuse_transmittance == 0.7
    assert NORMAL_TRANSMITTANCE == SINGLE.shortwave_beam_transmittance


def _covered(climate: dict[str, Any], cover: dict[str, Any] | None = None) -> ScenarioConfig:
    """The climate box as a scenario of its own, its cover described, its
    house air's parameters `climate`."""
    return ScenarioConfig.model_validate(
        BOX.model_dump()
        | {
            "greenhouse_id": "covered_box",
            "components": {"cover": cover or {"roof": TWIN_WALL}},
            "climate": climate,
        }
    )


def test_a_scenario_with_a_cover_runs_its_glass_and_its_light() -> None:
    """Its climate run's glass and its sunlight's are its cover's."""
    with Simulator(Catalogue()) as simulator:
        simulator.catalogue.register(_covered({"kind": "whole_house"}))
        day = climate_day(simulator, ("covered_box", "default", "default", (), (), (), ()))
        sunlight = plant_light(simulator, "covered_box", "default", "default").sunlight

        wind = day.run.weather.at(0.0).wind_speed_m_s
        assert day.glazing_at(0.0).u_w_m2k == pytest.approx(Glass.of(TWIN).u_in(wind))
        assert sunlight.glazing.diffuse_transmittance == 0.7
        assert sunlight.diffuse_passed == pytest.approx(0.7 * (1.0 - roof_shading(BOX.envelope)))


@pytest.mark.parametrize("house_air", ["grid", "whole_house"])
def test_a_scenario_giving_both_a_cover_and_the_glazings_u_is_refused(house_air: str) -> None:
    with pytest.raises(ValidationError) as refused:
        _covered({"kind": house_air, "glazing_u_w_m2k": 6.0})

    assert [error["msg"] for error in refused.value.errors()] == [
        "Value error, its components' cover and its house air's glazing_u_w_m2k each give "
        "its glass's U: one of them does"
    ]
    assert _covered({"kind": house_air}).cover == Cover.model_validate({"roof": TWIN_WALL})


def _manifest(parameters: dict[str, Any]) -> dict[str, Any]:
    """The climate box's manifest, its house's cover described, its house
    air's parameters `parameters`."""
    manifest: dict[str, Any] = json.loads((MANIFESTS_DIR / "climate_box.json").read_text())
    manifest = copy.deepcopy(manifest)
    manifest["installation"]["components"] = {"cover": {"roof": "single_glass"}}
    manifest["models"] = manifest.get("models", {}) | {
        "house_air": {"model": "grid", "parameters": parameters}
    }
    return manifest


def test_a_manifest_giving_both_is_refused_and_giving_the_cover_alone_runs() -> None:
    with pytest.raises(ValidationError, match="cover and its house air's glazing_u_w_m2k"):
        scenario_from_manifest("climate_box", _manifest({"glazing_u_w_m2k": 6.0}))

    config = scenario_from_manifest("climate_box", _manifest({"mixing_m2_s": 0.2}))

    assert config.cover == Cover(roof=CoverMaterialName.SINGLE_GLASS)
    assert isinstance(config.climate, GridAir)
    assert config.climate.mixing_m2_s == 0.2
    assert config.climate.model_fields_set == {"kind", "mixing_m2_s"}


def test_a_scenario_with_a_cover_writes_no_glazing_u_and_reads_back_the_same() -> None:
    config = _covered({"kind": "grid", "mixing_m2_s": 0.2})

    written = json.loads(export_scenario_file(config, with_recording=False))
    read = import_scenario_file(json.dumps(written)).config

    assert written["models"]["house_air"]["parameters"] == {
        name: value
        for name, value in config.climate.model_dump(mode="json", exclude={"kind"}).items()
        if name != "glazing_u_w_m2k"
    }
    assert read == config
