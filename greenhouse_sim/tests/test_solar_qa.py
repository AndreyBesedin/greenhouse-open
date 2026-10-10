"""The files P08's equinox views draw without the API (P08.9), and the sun's
light at reference points through the solar lab's clear equinox day.

`web/public/scenes/qa-solar-lab.json` is the solar lab's scene, and
`web/public/fields/qa-solar-lab-light.json` its weather, the sun's path
through its day, and the PAR on a level surface at each of its climate
grid's cells, at three moments: the morning (9:00), the sun's noon (12:50)
and the evening (16:30), on the site's clock. The viewer's solar QA page
(`/qa/solar-lab`) draws them from a fixed view for its screenshot tests.
Both are written here, from `greenhouse_sim/`:

    python tests/test_solar_qa.py --update

These tests fail if either drifts from what the simulator gives now. They
compare parsed JSON, so formatting does not count; numbers are rounded, as
platforms' maths libraries differ in the last bit.
"""

import json
import sys
from pathlib import Path
from typing import Final

import numpy as np
import pytest

from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services import scenarios, weather
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.world.geometry import Vector3

ROOT = Path(__file__).resolve().parents[1]
SCENE_FILE = ROOT / "web" / "public" / "scenes" / "qa-solar-lab.json"
LIGHT_FILE = ROOT / "web" / "public" / "fields" / "qa-solar-lab-light.json"
SCENARIO = "solar_lab"
DECIMALS = 6
# PAR is kept to hundredths of a µmol/m²/s, before it is written as 32-bit
# floats.
PAR_DECIMALS = 2
# The moments drawn, in seconds from the run's start, its site's midnight.
VIEWS: Final = {"morning": 9 * 3600, "noon": 12 * 3600 + 50 * 60, "evening": 16 * 3600 + 30 * 60}
# The PAR sensors either side of the crates, and two plants: the first,
# behind them, and the last, in the open.
SENSORS: Final = {
    "par_open": Vector3(x=3.05, y=1.5, z=0.3),
    "par_shade": Vector3(x=3.05, y=3.9, z=0.3),
}
PLANTS: Final = ("solar_lab_plant_001", "solar_lab_plant_016")
# The sun's light at those points and moments, as worked out when P08 was
# built: the outside's GHI, DNI and DHI (W/m²), the sensors' PAR and the
# plants' (µmol/m²/s). A change to the sun's model, the glass or the shade
# moves them, and should be meant.
REFERENCE: Final = {
    "morning": {
        "ghi": 306.178742,
        "dni": 657.365412,
        "dhi": 88.448592,
        "par_open": 483.219087,
        "par_shade": 289.752314,
        "solar_lab_plant_001": 139.278157,
        "solar_lab_plant_016": 529.328658,
    },
    "noon": {
        "ghi": 615.836107,
        "dni": 796.536759,
        "dhi": 125.718826,
        "par_open": 1068.7481,
        "par_shade": 197.966819,
        "solar_lab_plant_001": 197.966819,
        "solar_lab_plant_016": 1068.7481,
    },
    "evening": {
        "ghi": 329.44944,
        "dni": 676.108161,
        "dhi": 91.001456,
        "par_open": 534.980666,
        "par_shade": 347.554205,
        "solar_lab_plant_001": 569.108872,
        "solar_lab_plant_016": 307.066672,
    },
}


def _rounded(value: object, decimals: int = DECIMALS) -> object:
    if isinstance(value, float):
        return round(value, decimals)
    if isinstance(value, dict):
        return {key: _rounded(item, decimals) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item, decimals) for item in value]
    return value


def _scene() -> object:
    return _rounded(scenarios.initial_scene(SCENARIO).model_dump(mode="json"))


def _par_field(time_s: float) -> object:
    sunlight = plant_light(SCENARIO, DEFAULT_LAYOUT, DEFAULT_WEATHER).sunlight
    par = np.round(sunlight.at(time_s).par_umol_m2_s, PAR_DECIMALS)
    field = EnvironmentField(
        field_id=f"{SCENARIO}_light",
        source="solar:inside",
        grid=sunlight.grid,
        time_s=time_s,
        channels={AirQuantity.PAR: par},
    )
    return _rounded(field.document().model_dump(mode="json"))


def _light() -> object:
    return {
        "views": {
            name: {
                "weather": _rounded(weather.at_a_moment(SCENARIO, time_s).model_dump(mode="json")),
                "field": _par_field(time_s),
            }
            for name, time_s in VIEWS.items()
        },
        "day": _rounded(weather.through_the_day(SCENARIO).model_dump(mode="json")),
    }


def _par(field: EnvironmentField, point: Vector3) -> float:
    value = field.sample(AirQuantity.PAR, point)
    assert isinstance(value, float)
    return value


def _measured() -> dict[str, dict[str, float]]:
    """The sun's light at the reference points, at each moment drawn."""
    light = plant_light(SCENARIO, DEFAULT_LAYOUT, DEFAULT_WEATHER)
    measured = {}
    for name, time_s in VIEWS.items():
        outside = light.sunlight.outside_at(time_s)
        field = light.sunlight.at(time_s)
        grid = light.sunlight.grid
        channel = EnvironmentField(
            field_id="reference",
            source="solar:inside",
            grid=grid,
            time_s=time_s,
            channels={AirQuantity.PAR: field.par_umol_m2_s},
        )
        plants = light.par_at(time_s)
        measured[name] = {
            "ghi": outside.ghi_w_m2,
            "dni": outside.dni_w_m2,
            "dhi": outside.dhi_w_m2,
            **{sensor: _par(channel, point) for sensor, point in SENSORS.items()},
            **{plant: plants[plant] for plant in PLANTS},
        }
    return measured


def test_the_qa_scene_is_what_the_simulator_draws() -> None:
    assert json.loads(SCENE_FILE.read_text()) == _scene()


def test_the_qa_light_is_what_the_simulator_gives() -> None:
    assert json.loads(LIGHT_FILE.read_text()) == _light()


@pytest.mark.parametrize("view", VIEWS)
def test_the_suns_light_at_the_reference_points_is_as_recorded(view: str) -> None:
    assert _measured()[view] == pytest.approx(REFERENCE[view], rel=1e-6, abs=1e-6)


if __name__ == "__main__":
    if sys.argv[1:] == ["--measure"]:
        print(json.dumps(_measured(), indent=4))
        raise SystemExit(0)
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_solar_qa.py --update | --measure")
    SCENE_FILE.write_text(json.dumps(_scene(), indent=2) + "\n")
    LIGHT_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIGHT_FILE.write_text(json.dumps(_light()) + "\n")
    print("wrote", SCENE_FILE, LIGHT_FILE)
