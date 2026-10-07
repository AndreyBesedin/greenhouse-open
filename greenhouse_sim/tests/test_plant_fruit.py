"""How a fruit grows and ripens, and how its colour follows its ripeness."""

import math
from collections import Counter

import numpy as np
import pytest

from greenhouse_sim.biology.tomato.organ.development import DevelopmentParams, develop, emerged
from greenhouse_sim.biology.tomato.organ.fruit import (
    FruitParams,
    Maturity,
    fruit_mass_g,
    grown_fruit,
    maturity,
    set_fruit,
)
from greenhouse_sim.biology.tomato.organ.topology import (
    Fruit,
    FruitStage,
    Plant,
    change_problems,
)
from greenhouse_sim.scene.plants import FRUIT_COLOR, RIPENING_COLORS, fruit_color, plant_entities
from greenhouse_sim.scene.snapshot import SceneEntityKind
from greenhouse_sim.services import plants
from greenhouse_sim.world.geometry import Transform, Vector3

FRUITS = FruitParams()
PARAMS = DevelopmentParams()
PLANT = emerged("p01", PARAMS, seed=3)
# Long enough for a plant's first trusses to ripen.
RIPENING_CD = 1300.0
POPULATION = 60


def _fruits(plant: Plant) -> list[Fruit]:
    return [
        flower.fruit
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None
    ]


def _set(rank: int = 1, fruit_id: str = "p01_t01_fr01", born_tt: float = 500.0) -> Fruit:
    return set_fruit(PLANT, fruit_id, rank, born_tt, FRUITS)


def test_a_fruit_sets_small_and_grows_along_an_s_curve_to_its_final_size() -> None:
    fruit = _set()
    sizes = [
        grown_fruit(fruit, fruit.born_tt + FRUITS.growth_cd * step / 10, FRUITS).diameter_mm
        for step in range(11)
    ]

    assert fruit.diameter_mm == FRUITS.set_diameter_mm and fruit.ripeness == 0.0
    assert sizes[0] == pytest.approx(FRUITS.set_diameter_mm)
    assert sizes[-1] == pytest.approx(fruit.final_diameter_mm)
    assert sizes[5] == pytest.approx((FRUITS.set_diameter_mm + fruit.final_diameter_mm) / 2)
    gains = np.diff(sizes)
    assert (gains > 0).all() and gains[0] < gains[4] and gains[-1] < gains[5]
    later = grown_fruit(fruit, fruit.born_tt + 3 * FRUITS.growth_cd, FRUITS)
    assert later.diameter_mm == pytest.approx(fruit.final_diameter_mm)


def test_a_fruits_mass_follows_its_volume() -> None:
    assert fruit_mass_g(60.0, FRUITS) == pytest.approx(math.pi / 6 * 6.0**3)
    grown = grown_fruit(_set(), 2000.0, FRUITS)
    assert grown.mass_g == pytest.approx(fruit_mass_g(grown.diameter_mm, FRUITS))
    # A typical full-grown truss tomato weighs about 125 g.
    assert fruit_mass_g(FRUITS.final_diameter_mm, FRUITS) == pytest.approx(125, abs=10)


def test_final_sizes_vary_within_their_range_and_shrink_along_the_truss() -> None:
    reach = FRUITS.final_diameter_cv * FRUITS.limit_sd
    by_rank: dict[int, list[float]] = {}
    for place in range(200):
        for rank in (1, 6):
            fruit = _set(rank, f"p01_t{place:02d}_fr{rank:02d}")
            typical = FRUITS.final_diameter_mm * (1 - FRUITS.distal_size_decline * (rank - 1))
            assert typical * (1 - reach) <= fruit.final_diameter_mm <= typical * (1 + reach)
            by_rank.setdefault(rank, []).append(fruit.final_diameter_mm)

    assert np.mean(by_rank[1]) == pytest.approx(FRUITS.final_diameter_mm, rel=0.02)
    assert np.std(by_rank[1]) / np.mean(by_rank[1]) == pytest.approx(
        FRUITS.final_diameter_cv, rel=0.2
    )
    assert np.mean(by_rank[6]) < np.mean(by_rank[1])


def test_a_fruit_ripens_from_its_breaker_to_red_and_never_back() -> None:
    fruit = _set()
    breaker = fruit.breaker_tt

    def ripeness(thermal_time: float) -> float:
        return grown_fruit(fruit, thermal_time, FRUITS).ripeness

    assert ripeness(breaker) == 0.0
    assert ripeness(breaker + FRUITS.ripening_cd / 2) == pytest.approx(0.5)
    assert ripeness(breaker + FRUITS.ripening_cd) == 1.0
    assert ripeness(breaker + 5 * FRUITS.ripening_cd) == 1.0
    ripe = grown_fruit(fruit, breaker + FRUITS.ripening_cd, FRUITS)
    # Grown again to an earlier moment, a fruit does not unripen.
    assert grown_fruit(ripe, breaker, FRUITS).ripeness == 1.0


def test_each_fruit_draws_its_own_ripening_offset() -> None:
    offsets = [
        (_set(fruit_id=f"p01_t{place:02d}_fr01").breaker_tt - 500.0) / FRUITS.breaker_cd
        for place in range(200)
    ]
    reach = FRUITS.ripening_offset_cv * FRUITS.limit_sd

    assert min(offsets) >= 1 - reach and max(offsets) <= 1 + reach
    assert np.std(offsets) == pytest.approx(FRUITS.ripening_offset_cv, rel=0.2)
    assert _set().breaker_tt == _set().breaker_tt


@pytest.mark.parametrize(
    ("ripeness", "named"),
    [
        (0.0, Maturity.GREEN),
        (0.05, Maturity.BREAKER),
        (0.2, Maturity.TURNING),
        (0.5, Maturity.PINK),
        (0.7, Maturity.LIGHT_RED),
        (0.85, Maturity.RED),
        (1.0, Maturity.RED),
    ],
)
def test_a_fruits_maturity_class_follows_its_ripeness(ripeness: float, named: Maturity) -> None:
    assert maturity(ripeness) == named


def test_a_fruits_colour_runs_from_green_through_orange_to_red() -> None:
    assert fruit_color(0.0) == FRUIT_COLOR
    assert fruit_color(1.0) == RIPENING_COLORS[-1][1]
    reds = [fruit_color(step / 20).r for step in range(10)]
    greens = [fruit_color(step / 20).g for step in range(4, 21)]
    assert reds == sorted(reds)
    assert greens == sorted(greens, reverse=True)


def test_a_drawn_fruits_colour_and_sizes_are_its_biological_state() -> None:
    plant = plants.structure(80)
    fruits = {fruit.fruit_id: fruit for fruit in _fruits(plant)}
    entities = [
        e
        for e in plant_entities(plant, Transform(position=Vector3(x=0, y=0, z=0)))
        if e.kind == SceneEntityKind.FRUIT
    ]

    assert {e.properties["maturity"] for e in entities} > {"green", "red"}
    for entity in entities:
        fruit = fruits[str(entity.properties["organ_id"])]
        assert entity.color == fruit_color(fruit.ripeness)
        assert entity.properties["ripeness"] == round(fruit.ripeness, 2)
        assert entity.properties["mass_g"] == round(fruit.mass_g, 2)
        assert entity.properties["maturity"] == maturity(fruit.ripeness).value


def test_an_aborted_fruit_stays_as_it_was_when_it_dropped() -> None:
    grown = [develop(emerged("p01", PARAMS, seed), RIPENING_CD, PARAMS) for seed in range(60)]
    aborted = [f for plant in grown for f in _fruits(plant) if f.stage == FruitStage.ABORTED]
    trusses = PARAMS.trusses

    assert aborted
    for fruit in aborted:
        at_abortion = grown_fruit(
            fruit.model_copy(update={"stage": FruitStage.ATTACHED}),
            fruit.born_tt + trusses.fruit_abortion_cd,
            trusses.fruits,
        )
        assert fruit.diameter_mm == pytest.approx(at_abortion.diameter_mm)
        assert fruit.ripeness == 0.0


def test_the_labs_first_plant_ripens_its_lower_trusses_by_the_end_of_its_run() -> None:
    def tally(day: int) -> tuple[dict[str, int], int]:
        fruits = [f for f in _fruits(plants.structure(day)) if f.stage == FruitStage.ATTACHED]
        classes = Counter(maturity(f.ripeness).value for f in fruits)
        return dict(sorted(classes.items())), round(sum(f.mass_g for f in fruits))

    assert tally(60) == ({"green": 13}, 369)
    assert tally(75) == ({"green": 18, "light_red": 1, "pink": 1, "red": 1}, 984)
    assert tally(90) == ({"breaker": 1, "green": 17, "light_red": 1, "pink": 1, "red": 6}, 1534)


def test_shrinking_or_unripening_is_found_out() -> None:
    before = plants.structure(85)
    fruit = next(f for f in _fruits(before) if 0 < f.ripeness < 1)

    def changed(update: dict[str, float]) -> list[str]:
        stem = before.stem.model_copy(
            update={
                "phytomers": tuple(
                    p
                    if p.truss is None
                    else p.model_copy(
                        update={
                            "truss": p.truss.model_copy(
                                update={
                                    "flowers": tuple(
                                        flower
                                        if flower.fruit is None
                                        or flower.fruit.fruit_id != fruit.fruit_id
                                        else flower.model_copy(
                                            update={"fruit": fruit.model_copy(update=update)}
                                        )
                                        for flower in p.truss.flowers
                                    )
                                }
                            )
                        }
                    )
                    for p in before.stem.phytomers
                )
            }
        )
        return change_problems(before, before.model_copy(update={"stem": stem}))

    assert changed({"ripeness": fruit.ripeness / 2}) == [f"{fruit.fruit_id}'s ripeness went down"]
    assert changed({"diameter_mm": fruit.diameter_mm - 1}) == [
        f"{fruit.fruit_id}'s diameter_mm went down"
    ]
