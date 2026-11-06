"""The TOMGRO house's season (P14.10, decision 0060's milestone B):
Reduced-State TOMGRO grown by area on the reference greenhouse's rows,
through its season, and what it predicts, as the P14 roadmap documents it
(`docs/roadmap/archive/p14-models-by-manifest.md`, "Reduced-State TOMGRO in a
season"). Its numbers are predictions, never validated (milestone C): this
holds the documented ones to the run, so that a change to either is seen.
A season's run takes some two and a half minutes: marked slow, its first
days run beside it on every change.
"""

import sys
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.crop import of_plants, scenario_crop
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

SCENARIO: Final = "tomgro_house"
# The season's first days, run on their own: its house, site and weather.
FIRST_DAYS: Final = 2
# What the P14 roadmap's table documents, row by row, on the days it names:
# nodes, leaf area index (m² m⁻²), and the dry weights above ground, of the
# fruit and of the mature fruit (g m⁻² of floor).
DOCUMENTED: Final = {
    60: {
        "row_1": (24.85185049009185, 1.2368239481274375, 250.4963525227008, 8.922949410696171, 0.0),
        "row_2": (
            24.85185049009185,
            1.2368239481274375,
            212.3068976637428,
            6.4810619279639505,
            0.0,
        ),
    },
    120: {
        "row_1": (47.99005811081051, 4.0, 1365.5786664291413, 537.6051010279566, 398.0344123941974),
        "row_2": (47.99005811081051, 4.0, 1183.8391892974669, 467.029511284253, 337.09439896118033),
    },
}


def test_it_is_the_reference_greenhouses_house_and_season_but_for_its_crop() -> None:
    house, reference = SCENARIO_REGISTRY[SCENARIO], SCENARIO_REGISTRY["reference_greenhouse"]

    assert (house.envelope, house.layout, house.daily, house.control) == (
        reference.envelope,
        reference.layout,
        reference.daily,
        reference.control,
    )
    assert (house.start_date, house.duration_days) == (
        reference.start_date,
        reference.duration_days,
    )
    assert house.crop_model == "reduced_tomgro" and house.climate.kind == "whole_house"


def test_its_first_days_grow_each_rows_canopy_by_the_light_above_it() -> None:
    """What its season's run comes to, begun: a canopy by area on each row,
    each one growing, in as much of the house's light as reaches its row."""
    with simulator_of(cut(SCENARIO, days=FIRST_DAYS, season=True)) as simulator:
        crop = scenario_crop(simulator, RunRequest(SCENARIO))
        assert not of_plants(crop)
        planted, grown = crop.instances_on(0), crop.instances_on(FIRST_DAYS)
        light = {
            instance.scope_id: sum(
                hour.par_above_umol_m2_s
                for day in range(FIRST_DAYS)
                for hour in crop.course(instance.scope_id, day).hours
            )
            for instance in grown
        }

    rows = [instance.scope_id for instance in grown]
    assert rows == ["row_1", "row_2", "row_3", "row_4"]
    for before, after in zip(planted, grown, strict=True):
        assert after.state.n > before.state.n
        assert after.state.lai > before.state.lai
        assert after.state.w > before.state.w
    # Of the rows the sun reaches unequally, the one under more light is
    # heavier: which it is changes with the season.
    weights = {instance.scope_id: instance.state.w for instance in grown}
    for one, other in (("row_1", "row_2"), ("row_3", "row_4")):
        assert light[one] != light[other]
        assert (weights[one] < weights[other]) == (light[one] < light[other])


@pytest.mark.slow
def test_its_season_grows_its_canopy_full_and_its_fruit_mature_as_documented(
    simulator: Simulator,
) -> None:
    crop = scenario_crop(simulator, RunRequest(SCENARIO))
    assert not of_plants(crop)

    for day, rows in DOCUMENTED.items():
        grown = {instance.scope_id: instance.state for instance in crop.instances_on(day)}
        for row, (n, lai, w, wf, wm) in rows.items():
            state = grown[row]
            assert (state.n, state.lai, state.w, state.wf, state.wm) == pytest.approx(
                (n, lai, w, wf, wm), rel=1e-9
            ), f"day {day}, {row}: the P14 roadmap's table, written again from the run"
    last = crop.instances_on(SCENARIO_REGISTRY[SCENARIO].duration_days)
    # Its canopy full by the season's end, its fruit set and mature on every
    # row, the rows the light reaches less lighter.
    assert all(instance.state.lai == TomgroParameters().lai_max for instance in last)
    assert all(instance.state.wm > 0 for instance in last)
    weights = {instance.scope_id: instance.state.w for instance in last}
    assert weights["row_2"] < weights["row_1"] and weights["row_4"] < weights["row_3"]
    # The first days run on their own are this season's.
    with simulator_of(cut(SCENARIO, days=FIRST_DAYS, season=True)) as short:
        first_days = scenario_crop(short, RunRequest(SCENARIO))
        assert not of_plants(first_days)
        assert first_days.instances_on(FIRST_DAYS) == crop.instances_on(FIRST_DAYS)
