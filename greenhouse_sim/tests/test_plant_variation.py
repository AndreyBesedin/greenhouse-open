"""How plants of one crop differ: seeded, correlated variation of their
traits and organs, and the plant lab's row."""

import math
from http import HTTPStatus

import numpy as np
import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.tomato.organ.development import (
    DevelopmentParams,
    develop,
    emerged,
    final_size_fraction,
)
from greenhouse_sim.biology.tomato.organ.geometry import GOLDEN_ANGLE_RAD, PlantForm, organ_geometry
from greenhouse_sim.biology.tomato.organ.topology import Plant, PlantTraits, topology_problems
from greenhouse_sim.biology.tomato.organ.variation import (
    TraitSpread,
    VariationParams,
    draw_traits,
)
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.services import plants
from greenhouse_sim.world.geometry import Vector3

VARIATION = VariationParams()
CROP = DevelopmentParams()
# Enough plants for their spread to show, few enough for a quick test.
POPULATION = 400
Z = Vector3(x=0.0, y=0.0, z=1.0)


def _population(seed: int = 3) -> list[PlantTraits]:
    return [draw_traits(seed, f"p{place:03d}", VARIATION) for place in range(POPULATION)]


def _grown(traits: PlantTraits, thermal_time: float = 400.0, seed: int = 0) -> Plant:
    params = DevelopmentParams(organ_size_cv=0.08)
    return develop(emerged("p01", params, seed, traits), thermal_time, params)


def test_the_same_seed_gives_the_same_plants_and_geometry() -> None:
    first, again = plants.structure(20, 7, "p04"), plants.structure(20, 7, "p04")

    assert first == again
    assert organ_geometry(first) == organ_geometry(again)
    assert plants.scene(5, 7) == plants.scene(5, 7)


def test_another_seed_or_another_plant_differs() -> None:
    plant = plants.structure(20, 7, "p04")

    assert plants.structure(20, 8, "p04").traits != plant.traits
    assert plants.structure(20, 7, "p05").traits != plant.traits
    assert organ_geometry(plants.structure(20, 8, "p04")) != organ_geometry(plant)


def test_a_plants_draws_do_not_depend_on_which_other_plants_exist() -> None:
    alone = draw_traits(7, "p13", VARIATION)
    row = {plant_id: draw_traits(7, plant_id, VARIATION) for plant_id in plants.plant_ids()}

    assert row["p13"] == alone


def test_every_trait_stays_within_its_configured_range() -> None:
    population = _population()
    for name, spread in VARIATION.spreads().items():
        low, high = VARIATION.factor_range(spread)
        factors = [getattr(traits, f"{name}_scale") for traits in population]
        assert low <= min(factors) and max(factors) <= high, name
    vigours = [traits.vigour for traits in population]
    assert max(abs(vigour) for vigour in vigours) <= VARIATION.limit_sd
    assert all(0 <= traits.rotation_rad < 2 * math.pi for traits in population)


def test_traits_spread_about_a_typical_plant_as_configured() -> None:
    population = _population()
    for name, spread in VARIATION.spreads().items():
        factors = np.array([getattr(traits, f"{name}_scale") for traits in population])
        assert factors.mean() == pytest.approx(1.0, abs=0.02), name
        assert factors.std() == pytest.approx(spread.cv, rel=0.2), name
    rotations = np.array([traits.rotation_rad for traits in population])
    assert rotations.mean() == pytest.approx(math.pi, rel=0.15)


def test_traits_follow_vigour_as_their_loadings_say() -> None:
    population = _population()
    vigour = np.array([traits.vigour for traits in population])
    for name, spread in VARIATION.spreads().items():
        factors = np.array([getattr(traits, f"{name}_scale") for traits in population])
        correlation = float(np.corrcoef(vigour, factors)[0, 1])
        assert correlation == pytest.approx(spread.vigour_loading, abs=0.12), name


def test_a_spread_that_could_vary_a_trait_to_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="leaf_length could vary to nothing"):
        VariationParams(leaf_length=TraitSpread(cv=0.5))


def test_a_plants_traits_drive_its_development() -> None:
    typical = _grown(PlantTraits())
    quick = _grown(PlantTraits(phyllochron_scale=0.8))
    leafy = _grown(PlantTraits(leaf_length_scale=1.2, internode_length_scale=0.9))

    assert len(quick.stem.phytomers) > len(typical.stem.phytomers)
    for plain, varied in zip(typical.stem.phytomers, leafy.stem.phytomers, strict=True):
        assert varied.leaf.final_length_cm == pytest.approx(1.2 * plain.leaf.final_length_cm)
        assert varied.internode.final_length_cm == pytest.approx(
            0.9 * plain.internode.final_length_cm
        )


def test_an_organs_final_size_varies_around_its_plants() -> None:
    plant = _grown(PlantTraits(), thermal_time=2000.0, seed=5)
    full = [p for p in plant.stem.phytomers if final_size_fraction(p.rank, CROP) == 1.0]
    lengths = np.array([p.leaf.final_length_cm / CROP.leaf_length_cm for p in full])

    assert len(set(lengths)) == len(lengths)
    assert lengths.min() >= 1 - 0.08 * 2.5 and lengths.max() <= 1 + 0.08 * 2.5
    assert lengths.std() == pytest.approx(0.08, rel=0.35)
    # And from its own generator: the same organ of another plant draws anew.
    other = _grown(PlantTraits(), thermal_time=2000.0, seed=6)
    assert (
        other.stem.phytomers[-1].leaf.final_length_cm
        != plant.stem.phytomers[-1].leaf.final_length_cm
    )


def test_a_plants_traits_turn_it_and_change_how_it_holds_its_leaves() -> None:
    def petiole(traits: PlantTraits, rank: int = 1) -> Vector3:
        shapes = {s.shape_id: s for s in organ_geometry(_grown(traits))}
        return shapes[f"p01_n{rank:02d}_leaf_petiole"].transform.rotation.rotate(Z)

    typical = petiole(PlantTraits())
    turned = petiole(PlantTraits(rotation_rad=1.0))
    raised = petiole(PlantTraits(leaf_insertion_scale=1.2))

    assert math.atan2(typical.y, typical.x) == pytest.approx(0.0)
    assert math.atan2(turned.y, turned.x) == pytest.approx(1.0)
    second = petiole(PlantTraits(rotation_rad=1.0), rank=2)
    assert math.atan2(second.y, second.x) == pytest.approx(1.0 + GOLDEN_ANGLE_RAD - 2 * math.pi)
    assert math.asin(raised.z) == pytest.approx(1.2 * PlantForm().leaf_insertion_rad)


def test_the_labs_row_varies_and_keeps_every_rule() -> None:
    for day in (0, 30, 60):
        row = [plants.structure(day, plants.LAB_SEED, plant_id) for plant_id in plants.plant_ids()]
        assert all(topology_problems(plant) == [] for plant in row)
    heights = [sum(p.internode.length_cm for p in plant.stem.phytomers) for plant in row]
    counts = {len(plant.stem.phytomers) for plant in row}
    # Clearly not clones, yet one crop: within a third of the row's mean.
    assert max(heights) - min(heights) > 0.15 * np.mean(heights)
    assert max(heights) < 4 / 3 * np.mean(heights) and min(heights) > 2 / 3 * np.mean(heights)
    assert len(counts) > 1


def test_the_labs_scene_stands_its_row_along_y() -> None:
    scene = SceneSnapshot.model_validate(respond("GET", "/api/plants/scene?seed=7").body)
    bases = {
        e.properties["plant_id"]: e.transform.position
        for e in scene.entities
        if e.entity_id.endswith("_n01_internode")
    }

    assert sorted(bases) == plants.plant_ids()
    for place, plant_id in enumerate(plants.plant_ids()):
        assert bases[plant_id] == Vector3(x=0.0, y=place * plants.PLANT_SPACING_M, z=0.0)
    assert scene == plants.scene(0, 7)


def test_the_lab_answers_for_any_seed_and_plant_and_refuses_what_it_cannot() -> None:
    structure = respond("GET", "/api/plants/structure?day=3&seed=7&plant=p12")
    unknown = respond("GET", "/api/plants/structure?plant=p21")
    negative = respond("GET", "/api/plants/scene?seed=-1")
    wordy = respond("GET", "/api/plants/scene?seed=lucky")

    assert structure.status == HTTPStatus.OK
    assert Plant.model_validate(structure.body) == plants.structure(3, 7, "p12")
    assert (unknown.status, unknown.body) == (
        HTTPStatus.NOT_FOUND,
        {"error": "the plant lab has no plant 'p21'"},
    )
    assert (negative.status, negative.body) == (
        HTTPStatus.BAD_REQUEST,
        {"error": "a seed is a whole number from 0, not -1"},
    )
    assert (wordy.status, wordy.body) == (
        HTTPStatus.BAD_REQUEST,
        {"error": "seed wants a whole number, not 'lucky'"},
    )
