"""Vanthoor's model as the run grows it (P14.10, decision 0060): the
package's model agrees with the reference implementation on the
reproduction's own drivers, at every state and hour, within the
reproduction's tolerances; its parameters are the ones it reproduced
(`research/reproductions/vanthoor_katzin`, milestone A); and what a rung's
hour means change from those drivers is held to what was measured."""

import csv
import hashlib
import json
import math
import re
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.biology.area_contract import HourDrivers, StepCourse
from greenhouse_sim.biology.tomato.vanthoor.growth import (
    LEAF_HARVEST_MOST,
    fruit_harvest,
    leaf_pruning,
    live_hour,
    rates,
)
from greenhouse_sim.biology.tomato.vanthoor.parameters import (
    INITIAL_STATE,
    VanthoorParameters,
    VanthoorState,
)
from greenhouse_sim.core.drivers import HOUSE_HOURS
from greenhouse_sim.core.vanthoor_crop import VanthoorRung
from greenhouse_sim.domain.crop import Driver
from greenhouse_sim.units import HOUR_S

REPRODUCTIONS: Final = Path(__file__).resolve().parents[2] / "research" / "reproductions"
REPRODUCTION: Final = REPRODUCTIONS / "vanthoor_katzin"
# The reproduction's columns, by the package's state.
COLUMNS: Final = {
    "c_buf": "cBuf",
    "c_fruit": "cFruit",
    "c_leaf": "cLeaf",
    "c_stem": "cStem",
    "t_can_sum": "tCanSum",
    "t_can_24": "tCan24",
}
# What hour means change from the reference's forcing, measured on its
# season, its largest difference in mg CH₂O m⁻², and its largest share:
# - c_buf: 76 of 1,394 on day 112, and twice the buffer itself on day 54,
#   as it empties;
# - c_fruit: 714 of 278,758 on day 48, 0.68% on day 8;
# - c_leaf: 432 of 90,761 on day 22, 0.52% on day 15;
# - c_stem: 445 of 141,706 on day 50, 0.52% on day 15;
# - the fruit harvested: 1,815 of 604,489 on day 119, 0.30%, and 86% on
#   day 48, of the first small harvests.
MEANS_ABSOLUTE_MG_M2: Final = 100.0
MEANS_RELATIVE: Final = 0.01
HARVESTED_MEANS_ABSOLUTE_MG_M2: Final = 1000.0
# A mean keeps the temperature's integral, so its sum stays within the
# reproduction's tolerance; the filter moves within the hour, by 1e-3 °C at
# most.
SUM_MEANS_ABSOLUTE: Final = 1e-3
FILTER_MEANS_ABSOLUTE: Final = 1.5e-3
# The fruit harvested as a rate's integral, what left the fruit, against the
# trapezoid over the hours the reference's comparison declares: 237 of 307,614
# mg m⁻² on day 83, 200 of 612,525 at the end, as the rate moves within an
# hour.
INTEGRAL_ABSOLUTE_MG_M2: Final = 60.0
INTEGRAL_RELATIVE: Final = 1e-3


def _field(symbol: str) -> str:
    """The package's field of a published symbol, as the reproduction's
    manifest names it: `cFruitM` is `c_fruit_m`."""
    return re.sub(r"(?<!^)([A-Z])", r"_\1", symbol).lower()


def _manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((REPRODUCTION / "manifest.json").read_text())
    return loaded


def _moments() -> list[HourDrivers]:
    """The reproduction's drivers at each hourly moment, checked against the
    sha256 its manifest pins: the TOMGRO reproduction's numbers, in the
    columns the reference reads (`vanthoor_katzin/drivers.py`)."""
    with (REPRODUCTIONS / "reduced_tomgro" / "drivers.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))
    lines = ["Time,tCan,parGh,co2InPpm"]
    lines += [
        f"{((int(row['dat']) - 1) * 24 + int(row['hour'])) * round(HOUR_S)},"
        f"{row['tmean']},{row['rad']},{row['co2']}"
        for row in rows
    ]
    content = "\n".join(lines) + "\n"
    assert hashlib.sha256(content.encode()).hexdigest() == _manifest()["drivers"]["sha256"]
    return [
        HourDrivers(
            temperature_c=float(row["tmean"]),
            par_above_umol_m2_s=float(row["rad"]),
            co2_ppm=float(row["co2"]),
        )
        for row in rows
    ]


def _ramps() -> list[tuple[HourDrivers, HourDrivers]]:
    """Each hour's drivers as the reference forces it, from its start to its
    end: its first hour holds its first moment, as the reference does, and
    every later hour runs straight between its two."""
    moments = _moments()
    return [(moments[0], moments[0]), *pairwise(moments[1:])]


def _reference(name: str) -> list[dict[str, float]]:
    with (REPRODUCTION / "reference" / name).open(newline="") as file:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(file)]


def _harvested(rates_at_each_hour: list[float]) -> list[float]:
    """The fruit harvested the way the reproduction's comparison declares it,
    alike for both: its rate at each hourly moment, by the trapezoidal rule."""
    total = [0.0]
    for before, after in pairwise(rates_at_each_hour):
        total.append(total[-1] + (before + after) / 2 * HOUR_S)
    return total


def _reference_harvested(reference: list[dict[str, float]]) -> list[float]:
    return _harvested([row["mcFruitHar"] for row in reference])


def _season_as_the_reference_forces_it() -> list[VanthoorState]:
    parameters = VanthoorParameters()
    state = INITIAL_STATE
    season = [state]
    for start, end in _ramps():
        state = live_hour(state, start, end, parameters)
        season.append(state)
    return season


def test_its_parameters_and_its_start_are_the_published_ones() -> None:
    manifest = _manifest()
    parameters = VanthoorParameters()

    published = manifest["parameters"]
    assert {_field(symbol) for symbol in published} == set(VanthoorParameters.model_fields)
    for symbol, entry in published.items():
        assert getattr(parameters, _field(symbol)) == entry["value"], symbol
    for field, column in COLUMNS.items():
        assert getattr(INITIAL_STATE, field) == manifest["initial_state"][column]["value"], column
    assert INITIAL_STATE.harvested_fruit == 0.0


def test_its_rates_agree_with_the_reference_at_the_same_states() -> None:
    """No integration stands between them, so they are held as the
    reproduction's are: within its tolerances, at each of its half hours."""
    tolerances = _manifest()["rates"]["tolerances"]
    parameters = VanthoorParameters()
    ramps = _ramps()
    rows = _reference("rates.csv")

    assert len(rows) == len(ramps)
    for row, (start, end) in zip(rows, ramps, strict=True):
        found = rates(
            [*(row[column] for column in COLUMNS.values()), 0.0],
            (start.temperature_c + end.temperature_c) / 2,
            (start.par_above_umol_m2_s + end.par_above_umol_m2_s) / 2,
            (start.co2_ppm + end.co2_ppm) / 2,
            parameters,
        )
        for rate, column in zip(found, COLUMNS.values(), strict=False):
            assert rate == pytest.approx(
                row[f"rate_{column}"], rel=tolerances["relative"], abs=tolerances["absolute"]
            ), f"{column}'s rate at {row['Time']} s"


def test_it_agrees_with_the_reference_on_every_state_every_hour() -> None:
    """Within the reproduction's tolerances, `|ours - reference| <=
    max(absolute, relative * |reference|)`, on the reference's own forcing:
    the six states, the leaf area index and the fruit harvested, which the
    comparison declares as both implementations' trapezoid."""
    tolerances = _manifest()["compared"]["tolerances"]
    parameters = VanthoorParameters()
    reference = _reference("converged.csv")
    season = _season_as_the_reference_forces_it()

    assert len(season) == len(reference)
    harvested = _harvested([fruit_harvest(state.c_fruit, parameters) for state in season])
    theirs_harvested = _reference_harvested(reference)
    for hour, (ours, theirs) in enumerate(zip(season, reference, strict=True)):
        for field, column in COLUMNS.items():
            assert getattr(ours, field) == pytest.approx(
                theirs[column],
                rel=tolerances[column]["relative"],
                abs=tolerances[column]["absolute"],
            ), f"{column} at hour {hour}"
        assert ours.leaf_area_index(parameters) == pytest.approx(
            theirs["lai"], rel=tolerances["lai"]["relative"], abs=tolerances["lai"]["absolute"]
        ), f"the leaf area index at hour {hour}"
        assert harvested[hour] == pytest.approx(
            theirs_harvested[hour],
            rel=tolerances["harvested_fruit"]["relative"],
            abs=tolerances["harvested_fruit"]["absolute"],
        ), f"the fruit harvested at hour {hour}"


def test_the_fruit_harvested_it_keeps_is_what_left_the_fruit() -> None:
    """Its state integrates the rate as it integrates the fruit, where the
    reference's trapezoid over the hours runs ahead as the first harvests
    rise within an hour: a gap held to what was measured. The reference's
    season harvests, so a state that stayed at nothing fails."""
    season = _season_as_the_reference_forces_it()
    theirs = _reference_harvested(_reference("converged.csv"))

    for hour, (state, other) in enumerate(zip(season, theirs, strict=True)):
        assert state.harvested_fruit == pytest.approx(
            other, rel=INTEGRAL_RELATIVE, abs=INTEGRAL_ABSOLUTE_MG_M2
        ), f"hour {hour}"
    assert season[-1].harvested_fruit > 6e5


def test_its_leaves_are_pruned_by_a_smooth_switch_about_their_most() -> None:
    p = VanthoorParameters()

    at_most = leaf_pruning(p.c_leaf_max, p)

    assert at_most == pytest.approx(LEAF_HARVEST_MOST / 2)
    # At a leaf area index of 2.3, of a most of 3, some leaf is pruned still.
    assert 0 < leaf_pruning(p.c_leaf_max * 2.3 / 3, p) < at_most


def test_driven_by_hour_means_it_stays_within_what_the_means_change() -> None:
    """A rung is given each hour's mean, not its moments. Each hour's mean
    of the reference's forcing, through the rung, on every state and hour:
    what that moves, as measured."""
    rung = VanthoorRung(VanthoorParameters(), canopy_height_m=2.0)
    reference = _reference("converged.csv")
    state = rung.planted()
    season = [state]
    for start, end in _ramps():
        mean = HourDrivers(
            temperature_c=(start.temperature_c + end.temperature_c) / 2,
            par_above_umol_m2_s=(start.par_above_umol_m2_s + end.par_above_umol_m2_s) / 2,
            co2_ppm=(start.co2_ppm + end.co2_ppm) / 2,
        )
        state = rung.live_step(state, StepCourse(hours=(mean,)))
        season.append(state)

    theirs_harvested = _reference_harvested(reference)
    assert len(season) == len(reference)
    for hour, (ours, theirs) in enumerate(zip(season, reference, strict=True)):
        for field in ("c_buf", "c_fruit", "c_leaf", "c_stem"):
            column = COLUMNS[field]
            assert getattr(ours, field) == pytest.approx(
                theirs[column], rel=MEANS_RELATIVE, abs=MEANS_ABSOLUTE_MG_M2
            ), f"{column} at hour {hour}"
        assert ours.t_can_sum == pytest.approx(theirs["tCanSum"], abs=SUM_MEANS_ABSOLUTE)
        assert ours.t_can_24 == pytest.approx(theirs["tCan24"], abs=FILTER_MEANS_ABSOLUTE)
        assert ours.harvested_fruit == pytest.approx(
            theirs_harvested[hour], rel=MEANS_RELATIVE, abs=HARVESTED_MEANS_ABSOLUTE_MG_M2
        ), f"the fruit harvested at hour {hour}"


def test_its_steps_have_converged_on_a_brighter_warmer_season() -> None:
    """Where the reference's season does not go, the leaves and the fruit at
    their most through a season of strong light: the hour's twelve steps
    give what twice as many do, and stay finite and in bounds."""
    parameters = VanthoorParameters()

    def hour_of(index: int) -> HourDrivers:
        of_day = index % 24
        lit = 6 <= of_day < 18
        return HourDrivers(
            temperature_c=24.0 + 6.0 * math.sin(math.pi * (of_day - 8) / 12),
            par_above_umol_m2_s=1800.0 * math.sin(math.pi * (of_day - 5.5) / 12) if lit else 0.0,
            co2_ppm=1000.0,
        )

    twelve = twenty_four = INITIAL_STATE
    for index in range(120 * 24):
        hour = hour_of(index)
        twelve = live_hour(twelve, hour, hour, parameters)
        twenty_four = live_hour(twenty_four, hour, hour, parameters, steps=24)
        assert all(map(math.isfinite, twelve.model_dump().values())), f"hour {index}"

    assert twelve.leaf_area_index(parameters) < parameters.lai_max
    assert twelve.c_fruit < parameters.c_fruit_max
    # In its plateau, as far as the harvest and the pruning hold each.
    assert twelve.leaf_area_index(parameters) > 2.0
    assert twelve.c_fruit > 2.5e5
    for name, value in twelve.model_dump().items():
        assert value == pytest.approx(getattr(twenty_four, name), rel=1e-6, abs=1e-3), name


@pytest.mark.parametrize(
    ("state", "co2_ppm"),
    [
        (INITIAL_STATE, 0.0),
        (INITIAL_STATE.model_copy(update={"c_leaf": 0.0}), 420.0),
    ],
    ids=["no CO₂", "no leaves"],
)
def test_it_assimilates_nothing_where_the_equations_are_undefined(
    state: VanthoorState, co2_ppm: float
) -> None:
    """Eq 9.13 and 9.23 divide by the stomata's CO₂ and the leaf area: with
    neither, the light changes nothing."""
    parameters = VanthoorParameters()
    values = list(state.model_dump().values())

    lit = rates(values, 20.0, 800.0, co2_ppm, parameters)
    dark = rates(values, 20.0, 0.0, co2_ppm, parameters)

    assert all(map(math.isfinite, lit))
    assert lit == dark


def test_its_rung_steps_an_hour_and_the_profile_says_what_stands_for_the_canopy() -> None:
    rung = VanthoorRung(VanthoorParameters(), canopy_height_m=2.0)

    assert rung.step_s == HOUR_S
    assert HOUSE_HOURS.substitutes(rung.drivers) == {
        Driver.CANOPY_TEMPERATURE: Driver.AIR_TEMPERATURE
    }
