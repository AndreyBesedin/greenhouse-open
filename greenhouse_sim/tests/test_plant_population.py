"""The plant lab's crop over many seeds: its spread, its rates and its
yields stay within ranges a tomato crop plausibly takes, and its plants are
never clones. Four hundred plants grown for ninety days take a while, so
these tests are slow."""

import numpy as np
import pytest

from greenhouse_sim.biology.tomato.organ.development import develop, emerged, grow
from greenhouse_sim.biology.tomato.organ.fruit import Maturity, maturity
from greenhouse_sim.biology.tomato.organ.topology import (
    FlowerStage,
    FruitStage,
    Plant,
)
from greenhouse_sim.biology.tomato.organ.variation import draw_traits
from greenhouse_sim.services import plants

pytestmark = pytest.mark.slow

SEEDS = range(20)
REFERENCE = plants.ENVIRONMENTS[plants.REFERENCE]


def _height_cm(plant: Plant) -> float:
    return sum(phytomer.internode.length_cm for phytomer in plant.stem.phytomers)


def _crop() -> list[tuple[float, Plant, Plant]]:
    """Each plant's vigour, and the plant on days 60 and 90 of the lab's
    reference run."""
    crop = []
    for seed in SEEDS:
        for plant_id in plants.plant_ids():
            traits = draw_traits(seed, plant_id, plants.VARIATION)
            plant = emerged(plant_id, plants.DEVELOPMENT, seed, traits)
            transplant = develop(plant, plants.TRANSPLANT_CD, plants.DEVELOPMENT)
            day_60 = grow(transplant, [REFERENCE] * 60, plants.DEVELOPMENT)
            day_90 = grow(day_60, [REFERENCE] * 30, plants.DEVELOPMENT)
            crop.append((traits.vigour, day_60, day_90))
    return crop


CROP = _crop()


def test_every_plant_keeps_every_rule() -> None:
    for _, day_60, day_90 in CROP:
        assert day_60.problems() == [] and day_90.problems() == []


def test_plants_vary_in_height_but_stay_one_crop_and_are_never_clones() -> None:
    heights = np.array([_height_cm(day_60) for _, day_60, _ in CROP])

    assert 130 < heights.mean() < 180
    assert 0.08 < heights.std() / heights.mean() < 0.2
    assert heights.min() > 0.6 * heights.mean() and heights.max() < 1.5 * heights.mean()
    assert len(set(heights.round(9))) == len(CROP)


def test_vigorous_plants_grow_taller_and_carry_more_fruit() -> None:
    vigour = np.array([v for v, _, _ in CROP])
    heights = np.array([_height_cm(day_60) for _, day_60, _ in CROP])
    load = np.array(
        [
            sum(
                flower.fruit.mass_g
                for phytomer in day_90.stem.phytomers
                if phytomer.truss is not None
                for flower in phytomer.truss.flowers
                if flower.fruit is not None and flower.fruit.stage == FruitStage.ATTACHED
            )
            for _, _, day_90 in CROP
        ]
    )

    assert np.corrcoef(vigour, heights)[0, 1] > 0.5
    assert np.corrcoef(vigour, load)[0, 1] > 0.1


def test_development_runs_at_a_tomatos_pace() -> None:
    phytomers = np.array([len(day_60.stem.phytomers) for _, day_60, _ in CROP])
    trusses = np.array(
        [sum(p.truss is not None for p in day_90.stem.phytomers) for _, _, day_90 in CROP]
    )

    assert 25 < phytomers.mean() < 30 and 22 <= phytomers.min() and phytomers.max() <= 34
    assert 9 < trusses.mean() < 12 and trusses.min() >= 8


def test_flowers_set_and_fruits_ripen_at_a_plausible_rate_and_size() -> None:
    set_rates, reds, red_masses = [], [], []
    for _, _, day_90 in CROP:
        flowers = [
            flower
            for phytomer in day_90.stem.phytomers
            if phytomer.truss is not None
            for flower in phytomer.truss.flowers
        ]
        decided = [f for f in flowers if f.stage in {FlowerStage.SET, FlowerStage.ABORTED}]
        set_rates.append(sum(f.stage == FlowerStage.SET for f in decided) / len(decided))
        red = [
            f.fruit
            for f in flowers
            if f.fruit is not None
            and f.fruit.stage == FruitStage.ATTACHED
            and maturity(f.fruit.ripeness) == Maturity.RED
        ]
        reds.append(len(red))
        red_masses += [fruit.mass_g for fruit in red]

    assert 0.7 < np.mean(set_rates) < 0.84 and min(set_rates) > 0.4
    assert 6 < np.mean(reds) < 13 and min(reds) >= 1
    # Truss tomatoes of about a hundred grams: a truss's last fruits down to
    # about a quarter of that, its first, drawn large, up to about twice.
    assert 85 < np.mean(red_masses) < 115
    assert 15 < min(red_masses) and max(red_masses) < 250
