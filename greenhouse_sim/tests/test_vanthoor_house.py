"""The Vanthoor house's season (decision 0060's milestone B): Vanthoor's
model as Katzin simplified it, grown by area on the reference greenhouse's
rows, through its season, and what it predicts, as
`docs/research/tomato-models-in-the-run.md` documents it. Its numbers are
predictions, never validated (milestone C): this holds the documented ones
to the run, so that a change to either is seen. A season's run takes some
three minutes: marked slow, its first days run beside it on every change.
"""

import sys
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters, VanthoorState
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.crop import of_plants, scenario_crop
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

SCENARIO: Final = "vanthoor_house"
# The season's first days, run on their own: its house, site and weather.
FIRST_DAYS: Final = 2
# What the documented table gives, row by row, on the days it names: the
# buffer, the fruit, the leaves and the stems (mg CH₂O m⁻² of floor), the
# temperature sum (°C day), the canopy's temperature over the last day
# (°C), and the fruit harvested (mg CH₂O m⁻² of floor).
DOCUMENTED: Final = {
    60: {
        "row_1": (
            2026.780883727641,
            286929.8138784373,
            97355.03177019156,
            215694.55737769007,
            1072.6481059238886,
            19.501665777104506,
            273419.9400033144,
        ),
        "row_2": (
            229.46745895081492,
            284936.5400305191,
            96008.34301569143,
            201462.8628452878,
            1072.6481059238886,
            19.501665777104506,
            209933.13233518,
        ),
    },
    120: {
        "row_1": (
            10992.97944827567,
            286830.1801602153,
            97014.5885947383,
            313936.29920990736,
            2398.868220630045,
            23.162228913914923,
            1251924.280099719,
        ),
        "row_2": (
            10032.76259612956,
            286830.1785060857,
            97004.51649397948,
            282227.6876543389,
            2398.868220630045,
            23.162228913914923,
            1018002.7850098783,
        ),
    },
}


def _carbohydrate(state: VanthoorState) -> float:
    """All it holds, and has harvested, in mg CH₂O m⁻² of floor."""
    return state.c_buf + state.c_fruit + state.c_leaf + state.c_stem + state.harvested_fruit


def test_it_is_the_tomgro_house_but_for_its_crop_and_its_seed() -> None:
    house, tomgro = SCENARIO_REGISTRY[SCENARIO], SCENARIO_REGISTRY["tomgro_house"]

    assert house.model_copy(
        update={
            "greenhouse_id": tomgro.greenhouse_id,
            "name": tomgro.name,
            "description": tomgro.description,
            "crop_model": tomgro.crop_model,
            "crop": tomgro.crop,
            "random_seed": tomgro.random_seed,
        }
    ) == tomgro.model_copy(update={"layout": house.layout})
    assert house.layout == tomgro.layout
    assert house.crop_model == "vanthoor_katzin" and house.climate.kind == "whole_house"
    assert house.random_seed != tomgro.random_seed


def test_its_first_days_grow_each_rows_canopy_by_the_light_above_it() -> None:
    """What its season's run comes to, begun: a canopy by area on each row,
    its leaves and stems growing, and the row under more light holding more
    carbohydrate."""
    with simulator_of(cut(SCENARIO, days=FIRST_DAYS, season=True)) as simulator:
        crop = scenario_crop(simulator, RunRequest(SCENARIO))
        assert not of_plants(crop)
        planted, grown = crop.instances_on(0), crop.instances_on(FIRST_DAYS)
        light = {
            instance.scope_id: sum(
                crop.course(instance.scope_id, step).hours[0].par_above_umol_m2_s
                for step in range(FIRST_DAYS * crop.steps_a_day)
            )
            for instance in grown
        }

    rows = [instance.scope_id for instance in grown]
    assert rows == ["row_1", "row_2", "row_3", "row_4"]
    for before, after in zip(planted, grown, strict=True):
        assert after.state.c_leaf > before.state.c_leaf
        assert after.state.c_stem > before.state.c_stem
        assert after.state.t_can_sum > before.state.t_can_sum
    held = {instance.scope_id: _carbohydrate(instance.state) for instance in grown}
    for one, other in (("row_1", "row_2"), ("row_3", "row_4")):
        assert light[one] != light[other]
        assert (held[one] < held[other]) == (light[one] < light[other])


@pytest.mark.slow
def test_its_season_fills_its_canopy_and_harvests_its_fruit_as_documented(
    simulator: Simulator,
) -> None:
    crop = scenario_crop(simulator, RunRequest(SCENARIO))
    assert not of_plants(crop)

    for day, rows in DOCUMENTED.items():
        grown = {instance.scope_id: instance.state for instance in crop.instances_on(day)}
        for row, documented in rows.items():
            assert tuple(grown[row].model_dump().values()) == pytest.approx(documented, rel=1e-9), (
                f"day {day}, {row}: the documented table, written again from the run"
            )
    parameters = VanthoorParameters()
    last = crop.instances_on(SCENARIO_REGISTRY[SCENARIO].duration_days)
    # Its leaves short of their most, its fruit near its most unharvested,
    # harvested on every row, the rows the light reaches less harvesting less.
    assert all(2.0 < each.state.leaf_area_index(parameters) < parameters.lai_max for each in last)
    assert all(each.state.c_fruit > 0.9 * parameters.c_fruit_max for each in last)
    harvested = {each.scope_id: each.state.harvested_fruit for each in last}
    assert harvested["row_2"] < harvested["row_1"] and harvested["row_4"] < harvested["row_3"]
    # The first days run on their own are this season's.
    with simulator_of(cut(SCENARIO, days=FIRST_DAYS, season=True)) as short:
        first_days = scenario_crop(short, RunRequest(SCENARIO))
        assert not of_plants(first_days)
        assert first_days.instances_on(FIRST_DAYS) == crop.instances_on(FIRST_DAYS)
