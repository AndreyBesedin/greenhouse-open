"""The file P09's golden views of the reference greenhouse draw without the
API (P09.7), and the state probes checked beside them.

`web/public/scenes/qa-reference-greenhouse.json.gz` holds, gzipped, the
reference run at a few moments of its opening day, day 86, and on day 21:
for each, the house as the viewer draws it then (its equipment's levels and
its vents' openings, without its crop), the crop's day, the weather, the
climate field's channels that its views draw, what its vents pass, and its
state probes; and the crop, organ by organ, on each day drawn, and the sun's
path through day 86. Two moments branch an hour before the sun's noon: one
turns the fans off, one shuts the vents. The viewer's reference QA page
(`/qa/reference-greenhouse`) draws its golden views from it for its
screenshot tests. It is written here, from `greenhouse_sim/`, in about a
minute:

    python tests/test_reference_qa.py --update

and its probes printed, to pin below, with `--measure`. A slow test holds
the file to what the simulator gives now; numbers are rounded, as
platforms' maths libraries differ in the last bit.
"""

import gzip
import json
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

import numpy as np
import pytest

from greenhouse_sim.core.clock import DAY_S, days_ended
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.services import crop, fields, scenarios, weather
from greenhouse_sim.services.checkpoints import load_openings
from greenhouse_sim.services.run_state import run_state
from greenhouse_sim.services.runs import Commanded, RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.world.geometry import Vector3

ROOT = Path(__file__).resolve().parents[1]
QA_FILE = ROOT / "web" / "public" / "scenes" / "qa-reference-greenhouse.json.gz"
SCENARIO = "reference_greenhouse"
# Scenes are kept to a tenth of a millimetre, the rest to six decimals, and
# fields' values to thousandths, before they are written as 32-bit floats.
SCENE_DECIMALS = 4
DECIMALS = 6
FIELD_DECIMALS = 3
HOUR_S = 3600.0
MINUTE_S = 60.0
# The opening day, its dawn, the sun's noon (12:40 on the run's clock, its
# site's standard time) and its evening; and a young crop's day, at noon.
OPENING_DAY = 86
DAWN_S = OPENING_DAY * DAY_S + 6 * HOUR_S
NOON_S = OPENING_DAY * DAY_S + 12 * HOUR_S + 40 * MINUTE_S
EVENING_S = OPENING_DAY * DAY_S + 19 * HOUR_S + 30 * MINUTE_S
YOUNG_DAY = 21
YOUNG_S = YOUNG_DAY * DAY_S + 12 * HOUR_S + 40 * MINUTE_S
# The branches, an hour before the sun's noon: the fans off, the vents shut.
BRANCH_S = NOON_S - HOUR_S
FANS_OFF: Final = ((BRANCH_S, "fan_left", 0.0), (BRANCH_S, "fan_right", 0.0))
VENTS_SHUT: Final = tuple((BRANCH_S, f"roof_vent_{index}", 0.0) for index in (1, 2, 3))
# The anemometer's place, in the right fan's jet, where the jet is probed.
IN_THE_JET = Vector3(x=3.0, y=3.2, z=3.0)


@dataclass(frozen=True)
class Moment:
    """A moment of the reference run drawn: the commands its branch gives
    after its schedule's, the climate field's channels its views draw, and
    whether they draw what its vents pass."""

    time_s: float
    commands: tuple[Commanded, ...] = ()
    channels: tuple[AirQuantity, ...] = ()
    openings: bool = False


MOMENTS: Final = {
    "dawn": Moment(DAWN_S),
    "noon": Moment(
        NOON_S,
        channels=(AirQuantity.VELOCITY, AirQuantity.TEMPERATURE, AirQuantity.PAR),
        openings=True,
    ),
    "evening": Moment(EVENING_S),
    "fans-off": Moment(NOON_S, FANS_OFF, channels=(AirQuantity.VELOCITY,)),
    "vents-shut": Moment(NOON_S, VENTS_SHUT, channels=(AirQuantity.TEMPERATURE,), openings=True),
    "young": Moment(YOUNG_S),
}
# The probes at each moment, as worked out when P10.3 gave the run its
# season and its thermostat: the house's air (°C), the sun's elevation (°),
# the air's speed in the right fan's jet (m/s), what the vents exchange
# (m³/s), and the crop's leaves, fruits and red fruits. A change to any
# model they come from moves them, and should be meant.
CROP_ON_OPENING_DAY: Final = {"leaves": 10373.0, "fruits": 741.0, "red_fruits": 1.0}
REFERENCE: Final[dict[str, dict[str, float]]] = {
    "dawn": {"house_air_c": 15.754785, "sun_elevation_deg": 10.842524, **CROP_ON_OPENING_DAY},
    "noon": {
        "house_air_c": 28.136028,
        "sun_elevation_deg": 59.18513,
        "jet_m_s": 1.391237,
        "vents_exchange_m3_s": 1.07656,
        **CROP_ON_OPENING_DAY,
    },
    "evening": {"house_air_c": 16.152659, "sun_elevation_deg": 9.236631, **CROP_ON_OPENING_DAY},
    # The house as one volume does not feel its fans: only the jet stops.
    "fans-off": {
        "house_air_c": 28.136028,
        "sun_elevation_deg": 59.18513,
        "jet_m_s": 0.0,
        **CROP_ON_OPENING_DAY,
    },
    "vents-shut": {
        "house_air_c": 38.11858,
        "sun_elevation_deg": 59.18513,
        "vents_exchange_m3_s": 0.0,
        **CROP_ON_OPENING_DAY,
    },
    "young": {
        "house_air_c": 20.443174,
        "sun_elevation_deg": 38.727684,
        "leaves": 4257.0,
        "fruits": 0.0,
        "red_fruits": 0.0,
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


def _field(document: FieldDocument, kept: tuple[AirQuantity, ...]) -> object:
    """A field with only the channels its views draw, its values rounded."""
    field = EnvironmentField.from_document(document)
    rounded = EnvironmentField(
        field_id=field.field_id,
        source=field.source,
        grid=field.grid,
        time_s=field.time_s,
        channels={
            quantity: np.round(values, FIELD_DECIMALS)
            for quantity, values in field.channels.items()
            if quantity in kept
        },
    )
    return _rounded(rounded.document().model_dump(mode="json"))


def _speed(document: FieldDocument, point: Vector3) -> float:
    velocity = EnvironmentField.from_document(document).sample(AirQuantity.VELOCITY, point)
    assert isinstance(velocity, Vector3)
    return float(np.hypot(np.hypot(velocity.x, velocity.y), velocity.z))


def _crop_counts(simulator: Simulator, day: int) -> dict[str, float]:
    """How many leaves, fruits and red fruits the crop bears on a day."""
    entities = _crop_scene(simulator, day).entities
    fruits = [e for e in entities if e.properties.get("organ_kind") == "fruit"]
    return {
        "leaves": float(sum(e.properties.get("organ_kind") == "leaf" for e in entities)),
        "fruits": float(len(fruits)),
        "red_fruits": float(sum(e.properties.get("maturity") == "red" for e in fruits)),
    }


@cache
def _crop_scene(simulator: Simulator, day: int) -> SceneSnapshot:
    """The crop at noon on a day: it is the same through the day, as it has
    lived the days before."""
    return crop.crop_scene(
        simulator, RunRequest(SCENARIO), time_s=day * DAY_S + 12 * HOUR_S + 40 * MINUTE_S
    )


def _house(levels: dict[str, float]) -> object:
    """The house as the viewer draws it, its equipment at its levels and its
    doors and vents as open as they stand; without its crop, which the
    crop's day gives."""
    config = scenarios.scenario(PACKAGED, SCENARIO)
    equipment = {piece.actuator_id for piece in config.layout.equipment}
    scene = scenarios.initial_scene(
        PACKAGED,
        SCENARIO,
        scenarios.SceneChanges(
            levels={key: level for key, level in levels.items() if key in equipment},
            openings={key: level for key, level in levels.items() if key not in equipment},
        ),
    )
    house = scene.model_copy(
        update={"entities": [e for e in scene.entities if "organ_id" not in e.properties]}
    )
    return _rounded(house.model_dump(mode="json"), SCENE_DECIMALS)


def _moment(simulator: Simulator, moment: Moment) -> tuple[dict[str, Any], dict[str, float]]:
    """What a moment's views draw, and its probes."""
    run = RunRequest(SCENARIO, commands=moment.commands)
    state = run_state(simulator, run, until_s=moment.time_s)
    outside = weather.at_a_moment(PACKAGED, SCENARIO, moment.time_s)
    assert state.house_air is not None
    probes = {
        "house_air_c": state.house_air.temperature_c,
        "sun_elevation_deg": outside.sun.elevation_deg,
    }
    drawn: dict[str, Any] = {
        "time_s": moment.time_s,
        "house": _house(state.levels),
        "crop_day": days_ended(moment.time_s),
        "weather": _rounded(outside.model_dump(mode="json")),
    }
    if moment.channels:
        document = fields.field(simulator, run, "climate", time_s=moment.time_s)
        drawn["field"] = _field(document, moment.channels)
        if AirQuantity.VELOCITY in moment.channels:
            probes["jet_m_s"] = _speed(document, IN_THE_JET)
    if moment.openings:
        passing = fields.openings(simulator, run, time_s=moment.time_s)
        drawn["openings"] = _rounded(passing.model_dump(mode="json"))
        probes["vents_exchange_m3_s"] = sum((o.exchange_m3_s for o in passing.openings), 0.0)
    probes |= _crop_counts(simulator, days_ended(moment.time_s))
    return drawn, probes


@cache
def _document(simulator: Simulator) -> dict[str, Any]:
    """Everything the golden views draw, as the simulator gives it now."""
    load_openings(simulator)
    moments = {name: _moment(simulator, moment) for name, moment in MOMENTS.items()}
    days = sorted({days_ended(moment.time_s) for moment in MOMENTS.values()})
    return {
        "moments": {
            name: drawn | {"probes": _rounded(probes)} for name, (drawn, probes) in moments.items()
        },
        "crops": {
            str(day): _rounded(_crop_scene(simulator, day).model_dump(mode="json"), SCENE_DECIMALS)
            for day in days
        },
        "sun_path": _rounded(
            weather.through_the_day(PACKAGED, SCENARIO, time_s=OPENING_DAY * DAY_S).model_dump(
                mode="json"
            )
        ),
    }


def _kept() -> dict[str, Any]:
    kept: dict[str, Any] = json.loads(gzip.decompress(QA_FILE.read_bytes()))
    return kept


def test_the_kept_probes_are_as_recorded() -> None:
    moments = _kept()["moments"]
    assert set(moments) == set(MOMENTS) == set(REFERENCE)
    for name, reference in REFERENCE.items():
        assert moments[name]["probes"] == pytest.approx(reference, rel=1e-6, abs=1e-6), name


def test_the_kept_views_draw_what_they_say() -> None:
    kept = _kept()
    moments, crops = kept["moments"], kept["crops"]
    # Every moment's crop is kept, and the branches differ from the run only
    # where they say.
    assert {str(moment["crop_day"]) for moment in moments.values()} == set(crops)
    assert moments["noon"]["probes"]["jet_m_s"] > moments["fans-off"]["probes"]["jet_m_s"]
    assert moments["noon"]["probes"]["vents_exchange_m3_s"] > 0
    assert moments["vents-shut"]["probes"]["vents_exchange_m3_s"] == 0
    # The young crop bears no fruit; on the opening day the first is red.
    assert moments["young"]["probes"]["fruits"] == 0
    assert moments["noon"]["probes"]["red_fruits"] > 0


@pytest.mark.slow
def test_the_kept_views_are_what_the_simulator_gives(simulator: Simulator) -> None:
    assert _kept() == _document(simulator)


def _write(simulator: Simulator) -> None:
    text = json.dumps(_document(simulator), separators=(",", ":")) + "\n"
    QA_FILE.write_bytes(gzip.compress(text.encode(), compresslevel=9, mtime=0))


if __name__ == "__main__":
    with Simulator() as simulator:
        if sys.argv[1:] == ["--measure"]:
            print(
                json.dumps(
                    {name: m["probes"] for name, m in _document(simulator)["moments"].items()},
                    indent=4,
                )
            )
            raise SystemExit(0)
        if sys.argv[1:] != ["--update"]:
            raise SystemExit("usage: python tests/test_reference_qa.py --update | --measure")
        _write(simulator)
        print("wrote", QA_FILE)
