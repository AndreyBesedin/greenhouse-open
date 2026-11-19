"""The weather's sky and its diffuse light (P24.2, decision 0078): a recorded
weather may give the sky's downward longwave, its effective temperature and
the measured diffuse radiation, each read in its unit and refused outside its
range by its column. A weather that gives none of them reads, and is
digested, as before; no other weather gives them; a weather station reads
them only where the weather gives them; and neither house air model reads
them."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.enums import ObservationType

from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.climate.settings import WholeHouseAir
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.sensors.air import OBSERVATION_TYPES, WEATHER_QUANTITIES, observe, reads
from greenhouse_sim.services import weather
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.solar.sky import cloud_factor
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.weather.recorded import (
    PREFIX,
    RANGES,
    RECORDED_DIRECTORY,
    SKY_TEMPERATURE_RANGE_C,
    RecordedWeather,
    WeatherFileError,
    checked_recording,
    read_records,
)
from greenhouse_sim.weather.sources import Clouded, interpolated
from greenhouse_sim.weather.state import RECORDED_ONLY, WeatherState
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.sensors import PointSensor
from greenhouse_sim.world.site import DEFAULT_SITE

BOX = SCENARIO_REGISTRY["climate_box"]
HEADER = "timestamp,outside_air_temperature_c,outside_relative_humidity_pct"
SKY = ",outside_downward_longwave_w_m2,outside_sky_temperature_c,outside_diffuse_radiation_w_m2"
# What a state held before P24.2, and still holds for a weather without them.
WRITTEN_BEFORE = {
    "air_temperature_c",
    "relative_humidity_pct",
    "co2_ppm",
    "wind_speed_m_s",
    "wind_direction_deg",
    "global_radiation_w_m2",
    "cloud_cover_pct",
    "barometric_pressure_hpa",
}
# The weather a packaged scenario's run is under through its first day, as
# its digest was before the sky's quantities were added (main at b3a0c354).
DIGESTS_BEFORE = [
    ("climate_box", None, "fd83ed94ea6b9ddae2728d2ea790724ff90c8d458f2f9144995190c0ca6eb338"),
    (
        "climate_box",
        "cold_spring_day",
        "cd9f7232657f16febeca24c03c4262f7138fec11de84b685e6d3d6c4dbdcd1bd",
    ),
    (
        "climate_box",
        "example_day",
        "d1b5b05c6ab29a22c1228b32147d4bc4e3b45a5e1d6bbe2546a3418b7ad64391",
    ),
    (
        "reference_greenhouse",
        None,
        "54afbe65a291a728963847735138fc82e631d5d9d41b43c56ca0df1d77f14102",
    ),
]
# Stefan and Boltzmann's constant, W/m²K⁴ (CODATA 2018), and 0 °C in kelvin.
SIGMA = 5.670374419e-8
KELVIN = 273.15


def _source(text: str) -> Callable[[datetime], WeatherState]:
    return RecordedWeather(file="day.csv", text=text).source(DEFAULT_SITE).at


def _at(hour: float) -> datetime:
    return datetime(2026, 4, 1, tzinfo=UTC) + timedelta(hours=hour)


def test_a_recording_gives_the_sky_and_the_diffuse_light_in_their_units() -> None:
    at = _source(
        HEADER + SKY + "\n2026-04-01T00:00Z,8,90,290,-5.5,0\n2026-04-01T01:00Z,8,90,310,-2.5,60\n",
    )

    start, halfway = at(_at(0)), at(_at(0.5))
    assert (start.downward_longwave_w_m2, start.sky_temperature_c) == (290.0, -5.5)
    assert start.diffuse_radiation_w_m2 == 0.0
    # Each between its known values, linearly.
    assert halfway.downward_longwave_w_m2 == pytest.approx(300.0)
    assert halfway.sky_temperature_c == pytest.approx(-4.0)
    assert halfway.diffuse_radiation_w_m2 == pytest.approx(30.0)
    assert set(halfway.model_dump(mode="json")) == WRITTEN_BEFORE | set(RECORDED_ONLY)


@pytest.mark.parametrize(
    ("cells", "refusal"),
    [
        ("39.5,,", "outside_downward_longwave_w_m2 is 39.5, outside 40 to 700"),
        ("700.5,,", "outside_downward_longwave_w_m2 is 700.5, outside 40 to 700"),
        (",-110.5,", "outside_sky_temperature_c is -110.5, outside -110 to 60"),
        (",60.5,", "outside_sky_temperature_c is 60.5, outside -110 to 60"),
        (",,-0.5", "outside_diffuse_radiation_w_m2 is -0.5, outside 0 to 1500"),
        (",,1500.5", "outside_diffuse_radiation_w_m2 is 1500.5, outside 0 to 1500"),
    ],
)
def test_a_value_outside_its_range_is_refused_by_its_column(cells: str, refusal: str) -> None:
    with pytest.raises(WeatherFileError, match=f"row 3: {refusal}"):
        read_records(
            HEADER + SKY + f"\n2026-04-01T00:00Z,8,90,,,\n2026-04-01T01:00Z,8,90,{cells}\n"
        )


def test_each_ranges_ends_are_read() -> None:
    known = read_records(
        HEADER + SKY + "\n2026-04-01T00:00Z,8,90,40,-110,0\n2026-04-01T01:00Z,8,90,700,60,1500\n"
    )

    assert known["downward_longwave_w_m2"].values == [40.0, 700.0]
    assert known["sky_temperature_c"].values == [-110.0, 60.0]
    assert known["diffuse_radiation_w_m2"].values == [0.0, 1500.0]


def test_the_sky_temperatures_range_is_a_black_body_radiating_the_longwaves() -> None:
    # The BSRN's limits for the downward longwave, 40 and 700 W/m², are a
    # black body's at -110.18 and 60.18 °C; the range lies within them.
    coldest, warmest = ((w / SIGMA) ** 0.25 - KELVIN for w in RANGES["downward_longwave_w_m2"])

    assert coldest == pytest.approx(-110.178, abs=1e-3)
    assert warmest == pytest.approx(60.178, abs=1e-3)
    low, high = SKY_TEMPERATURE_RANGE_C
    assert coldest < low < coldest + 0.5
    assert warmest - 0.5 < high < warmest


def test_neither_of_the_skys_is_worked_out_from_the_other() -> None:
    longwave = _source(
        HEADER + ",outside_downward_longwave_w_m2\n2026-04-01T00:00Z,8,90,300\n",
    )(_at(0))

    assert longwave.downward_longwave_w_m2 == 300.0
    assert longwave.sky_temperature_c is None
    assert longwave.diffuse_radiation_w_m2 is None


def test_a_recording_without_them_reads_and_is_written_as_before() -> None:
    state = _source(HEADER + "\n2026-04-01T00:00Z,8,90\n")(_at(0))

    assert all(getattr(state, name) is None for name in RECORDED_ONLY)
    assert set(state.model_dump(mode="json")) == WRITTEN_BEFORE


@pytest.mark.parametrize(("scenario_id", "under", "digest"), DIGESTS_BEFORE)
def test_a_packaged_scenarios_weather_has_the_digest_it_had(
    scenario_id: str, under: str | None, digest: str
) -> None:
    assert weather.series_sha256(PACKAGED, scenario_id, under, DAY_S) == digest


def test_where_a_recording_does_not_know_them_it_gives_none_and_the_run_goes_on() -> None:
    at = _source(
        HEADER
        + SKY
        + "\n2026-04-01T00:00Z,8,90,,,\n2026-04-01T01:00Z,8,90,300,-4,10"
        + "\n2026-04-01T01:30Z,8,90,,,\n2026-04-01T02:00Z,8,90,320,-2,30"
        + "\n2026-04-01T03:00Z,8,90,,,\n2026-04-01T04:00Z,8,90,,,"
        + "\n2026-04-01T05:00Z,8,90,340,0,50\n2026-04-01T06:00Z,8,90,,,\n",
    )

    # Before its first value, across a gap of three hours and after its last.
    for hour in (0.5, 3.5, 5.5):
        state = at(_at(hour))
        assert state.air_temperature_c == 8.0
        assert all(getattr(state, name) is None for name in RECORDED_ONLY)
    # A gap of an hour is interpolated across, as any quantity's is.
    assert at(_at(1.5)).downward_longwave_w_m2 == pytest.approx(310.0)


@pytest.mark.parametrize(
    ("scenario_id", "under"),
    [("climate_box", None), ("climate_box", "cold_spring_day"), ("reference_greenhouse", None)],
    ids=["constant", "synthetic", "seasonal"],
)
def test_no_weather_but_a_recording_gives_them(scenario_id: str, under: str | None) -> None:
    day = weather.through_the_day(PACKAGED, scenario_id, under)

    assert {getattr(state, name) for state in day.weather for name in RECORDED_ONLY} == {None}


def test_between_two_states_each_is_given_where_both_give_it() -> None:
    earlier = WeatherState(
        barometric_pressure_hpa=1000.0, downward_longwave_w_m2=300.0, sky_temperature_c=-4.0
    )
    later = WeatherState(
        barometric_pressure_hpa=1000.0, downward_longwave_w_m2=320.0, diffuse_radiation_w_m2=40.0
    )

    between = interpolated(earlier, later, 0.25)
    assert between.downward_longwave_w_m2 == pytest.approx(305.0)
    assert between.sky_temperature_c is None
    assert between.diffuse_radiation_w_m2 is None


def test_under_other_clouds_a_recordings_sky_is_not_given() -> None:
    clear = WeatherState(
        barometric_pressure_hpa=1000.0,
        global_radiation_w_m2=500.0,
        downward_longwave_w_m2=280.0,
        sky_temperature_c=-12.0,
        diffuse_radiation_w_m2=80.0,
    )

    class _Recorded:
        def at(self, moment: datetime) -> WeatherState:
            return clear

    state = Clouded(source=_Recorded(), cloud_cover_pct=50.0).at(_at(12))
    # Its sun dimmed as any weather's is, from a clear sky's to half covered.
    assert state.global_radiation_w_m2 == pytest.approx(500.0 * cloud_factor(50.0))
    assert all(getattr(state, name) is None for name in RECORDED_ONLY)


INSTRUMENTS = {
    SensorKind.DOWNWARD_LONGWAVE: ("W/m²", ObservationType.OUTSIDE_DOWNWARD_LONGWAVE_W_M2, 300.0),
    SensorKind.SKY_TEMPERATURE: ("°C", ObservationType.OUTSIDE_SKY_TEMPERATURE_C, -4.0),
    SensorKind.DIFFUSE_RADIATION: ("W/m²", ObservationType.OUTSIDE_DIFFUSE_RADIATION_W_M2, 45.0),
}
STATION = [
    PointSensor(sensor_id=f"station_{kind}", kind=kind, position=Vector3(x=-3.0, y=0.0, z=2.0))
    for kind in INSTRUMENTS
]
UNDER_THE_SKY = WeatherState(
    barometric_pressure_hpa=1000.0,
    downward_longwave_w_m2=300.0,
    sky_temperature_c=-4.0,
    diffuse_radiation_w_m2=45.0,
)


def test_a_station_reads_them_only_where_the_weather_gives_them() -> None:
    field = shear_field("shear", air_grid(BOX))
    without = UNDER_THE_SKY.model_copy(update=dict.fromkeys(RECORDED_ONLY))

    for instrument in STATION:
        unit, observation_type, value = INSTRUMENTS[instrument.kind]
        assert instrument.reads_the_weather()
        assert (instrument.unit(), OBSERVATION_TYPES[instrument.kind]) == (unit, observation_type)
        assert reads(instrument, field, UNDER_THE_SKY) == value
        assert reads(instrument, field, without) is None


@pytest.mark.parametrize("given", [True, False])
def test_its_readings_are_the_protocols_outside_observations_where_given(given: bool) -> None:
    outside = (
        UNDER_THE_SKY if given else UNDER_THE_SKY.model_copy(update=dict.fromkeys(RECORDED_ONLY))
    )
    field = shear_field("shear", air_grid(BOX))
    observed = observe(
        STATION,
        lambda _: field,
        120,
        start=BOX.run_start(),
        greenhouse_id="climate_box",
        run_id="run",
        weather_at=lambda _: outside,
    )

    assert check_observations(observed) == []
    assert sorted((o.observation_type, o.value) for o in observed) == (
        sorted((t, v) for _, t, v in INSTRUMENTS.values() for _ in range(3)) if given else []
    )


def test_each_recorded_quantity_is_an_outside_observation_type() -> None:
    """The same name means the same in a record, a file and a run: each of a
    file's columns, and what each of a station's instruments reports."""
    assert {ObservationType(PREFIX + name) for name in RANGES} >= {
        ObservationType.OUTSIDE_DOWNWARD_LONGWAVE_W_M2,
        ObservationType.OUTSIDE_SKY_TEMPERATURE_C,
        ObservationType.OUTSIDE_DIFFUSE_RADIATION_W_M2,
    }
    for kind, quantity in WEATHER_QUANTITIES.items():
        assert OBSERVATION_TYPES[kind] == PREFIX + quantity


# Moments in the air's first two hours, which the grid works out cell by
# cell, and after them.
MOMENTS_S = (0.5 * HOUR_S, 1.5 * HOUR_S, 2.5 * HOUR_S, 9.0 * HOUR_S)


def _with_the_sky(text: str) -> str:
    """A recording with the sky's quantities and the diffuse light added to
    each of its rows, each changing through the day."""
    header, *rows = text.strip().split("\n")
    return (
        "\n".join(
            [header + SKY]
            + [f"{row},{280 + i % 50},{-9 + i % 12},{i % 300}" for i, row in enumerate(rows)]
        )
        + "\n"
    )


@pytest.mark.parametrize("model", ["grid", "whole_house"])
def test_neither_house_air_model_reads_them(model: str) -> None:
    example = (RECORDED_DIRECTORY / "example_day.csv").read_text()
    house = (
        BOX
        if model == "grid"
        else BOX.model_copy(
            update={
                "climate": WholeHouseAir.model_validate(
                    BOX.climate.model_dump(exclude={"kind", "mixing_m2_s"})
                )
            }
        )
    )
    plain = house.model_copy(update={"weather": RecordedWeather(file="example_day.csv")})
    sky = house.model_copy(
        update={"weather": checked_recording("sky_day.csv", _with_the_sky(example).encode())}
    )
    assert sky.run_weather().at(HOUR_S).downward_longwave_w_m2 is not None

    def run(config: ScenarioConfig) -> tuple[str, list[HouseAir], list[np.ndarray]]:
        with Simulator(Catalogue(PACKAGED.with_config(config))) as simulator:
            _, run_id = air_through_a_run(simulator, RunRequest("climate_box"))
            _, day = climate_run(simulator, RunRequest("climate_box"))
            return (
                run_id,
                [day.house.air_at(time_s) for time_s in MOMENTS_S],
                [
                    day.field("climate_box_climate", time_s).channels[AirQuantity.TEMPERATURE]
                    for time_s in MOMENTS_S
                ],
            )

    (plain_id, plain_houses, plain_cells), (sky_id, sky_houses, sky_cells) = run(plain), run(sky)
    # Another weather, so another run, with the same air.
    assert plain_id != sky_id
    assert sky_houses == plain_houses
    assert all(np.array_equal(a, b) for a, b in zip(sky_cells, plain_cells, strict=True))
    # An air that changes through the day.
    assert plain_houses[0].temperature_c != plain_houses[-1].temperature_c
