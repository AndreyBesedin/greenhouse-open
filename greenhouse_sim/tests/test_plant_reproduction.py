"""Trusses, flowers and fruit set: when they appear, how flowers set or abort,
and that every organ keeps its identity and changes stage only as allowed."""

from collections import Counter

import pytest
from pydantic import ValidationError

from greenhouse_sim.biology.tomato.organ.development import (
    DevelopmentParams,
    develop,
    emerged,
    grow,
)
from greenhouse_sim.biology.tomato.organ.geometry import (
    BUD_RADIUS_M,
    FLOWER_RADIUS_M,
    FLOWER_SPACING_M,
    METRES_PER_MM,
    organ_geometry,
)
from greenhouse_sim.biology.tomato.organ.reproduction import TrussParams, bears_truss
from greenhouse_sim.biology.tomato.organ.topology import (
    Flower,
    FlowerStage,
    Fruit,
    FruitStage,
    LeafStage,
    Plant,
    Truss,
    change_problems,
    topology_problems,
)
from greenhouse_sim.scene.plants import BUD_COLOR, FLOWER_COLOR, plant_entities
from greenhouse_sim.scene.snapshot import SceneEntityKind
from greenhouse_sim.services import plants
from greenhouse_sim.world.geometry import Cylinder, Sphere, Transform, Vector3

PARAMS = DevelopmentParams()
TRUSSES = PARAMS.trusses
# Long enough for a plant to set fruit on several trusses.
FRUITING_CD = 900.0
# Enough plants for set and abortion rates to show.
POPULATION = 150


def _fruiting(seed: int, plant_id: str = "p01", thermal_time: float = FRUITING_CD) -> Plant:
    return develop(emerged(plant_id, PARAMS, seed), thermal_time, PARAMS)


def _trusses(plant: Plant) -> list[Truss]:
    return [p.truss for p in plant.stem.phytomers if p.truss is not None]


def _flowers(plant: Plant) -> list[Flower]:
    return [flower for truss in _trusses(plant) for flower in truss.flowers]


def _fruits(plant: Plant) -> list[Fruit]:
    return [flower.fruit for flower in _flowers(plant) if flower.fruit is not None]


def _with_stage(plant: Plant, rank: int, update: dict[str, object]) -> Plant:
    phytomers = list(plant.stem.phytomers)
    phytomer = phytomers[rank - 1]
    phytomers[rank - 1] = phytomer.model_copy(update=update)
    stem = plant.stem.model_copy(update={"phytomers": tuple(phytomers)})
    return plant.model_copy(update={"stem": stem})


def test_trusses_appear_on_their_phytomers_and_are_numbered_from_the_bottom() -> None:
    plant = _fruiting(seed=1)
    bearing = [p.rank for p in plant.stem.phytomers if p.truss is not None]

    assert bearing == [rank for rank in range(1, 30) if bears_truss(rank, TRUSSES)][: len(bearing)]
    assert bearing[:3] == [8, 11, 14]
    assert [truss.number for truss in _trusses(plant)] == list(range(1, len(bearing) + 1))
    for phytomer in plant.stem.phytomers:
        if phytomer.truss is not None:
            assert phytomer.truss.born_tt == phytomer.born_tt
    assert topology_problems(plant) == []


def test_a_truss_bears_its_drawn_number_of_flowers_one_after_another() -> None:
    counts = Counter(
        truss.final_flower_count for seed in range(30) for truss in _trusses(_fruiting(seed))
    )
    plant = _fruiting(seed=1)
    first = _trusses(plant)[0]

    assert set(counts) == set(range(TRUSSES.min_flowers, TRUSSES.max_flowers + 1))
    assert len(first.flowers) == first.final_flower_count
    assert [flower.flower_id for flower in first.flowers] == [
        f"p01_t01_fl{rank:02d}" for rank in range(1, first.final_flower_count + 1)
    ]
    for flower in first.flowers:
        assert flower.born_tt == pytest.approx(
            first.born_tt + (flower.rank - 1) * TRUSSES.flower_interval_cd
        )
    assert _fruiting(seed=1) == plant


def test_a_flower_is_a_bud_then_opens_then_sets_or_aborts_at_its_moments() -> None:
    plant = _fruiting(seed=1, thermal_time=0.0)
    first_truss_born = (TRUSSES.first_truss_rank - 1) * PARAMS.phyllochron_cd
    opens = first_truss_born + TRUSSES.anthesis_cd
    decided = opens + TRUSSES.set_decision_cd

    def stage(thermal_time: float) -> FlowerStage:
        grown = develop(plant, thermal_time, PARAMS)
        return _trusses(grown)[0].flowers[0].stage

    assert stage(opens - 1) == FlowerStage.BUD
    assert stage(opens) == FlowerStage.OPEN
    assert stage(decided - 1) == FlowerStage.OPEN
    assert stage(decided) in {FlowerStage.SET, FlowerStage.ABORTED}


def test_a_set_flowers_fruit_takes_its_place_and_appears_when_it_set() -> None:
    plant = _fruiting(seed=1)
    for truss in _trusses(plant):
        for flower in truss.flowers:
            if flower.stage != FlowerStage.SET:
                assert flower.fruit is None
                continue
            assert flower.fruit is not None
            assert flower.fruit.fruit_id == f"p01_t{truss.number:02d}_fr{flower.rank:02d}"
            assert flower.fruit.born_tt == pytest.approx(
                flower.born_tt + TRUSSES.anthesis_cd + TRUSSES.set_decision_cd
            )
            assert flower.fruit.diameter_mm >= TRUSSES.fruits.set_diameter_mm


def test_flowers_near_a_trusss_base_set_more_often_than_those_at_its_tip() -> None:
    decided: Counter[int] = Counter()
    set_: Counter[int] = Counter()
    for seed in range(POPULATION):
        for flower in _flowers(_fruiting(seed)):
            if flower.stage in {FlowerStage.SET, FlowerStage.ABORTED}:
                decided[flower.rank] += 1
                set_[flower.rank] += flower.stage == FlowerStage.SET

    for rank in (1, 2, 3, 4):
        assert set_[rank] / decided[rank] == pytest.approx(TRUSSES.set_probability(rank), abs=0.06)
    assert set_[1] / decided[1] > set_[4] / decided[4]


def test_a_young_fruit_aborts_now_and_then_and_stays_aborted() -> None:
    fruits = [fruit for seed in range(POPULATION) for fruit in _fruits(_fruiting(seed))]
    decided = [f for f in fruits if f.born_tt + TRUSSES.fruit_abortion_cd <= FRUITING_CD]
    aborted = [f for f in decided if f.stage == FruitStage.ABORTED]

    assert len(decided) > 500
    assert len(aborted) / len(decided) == pytest.approx(
        TRUSSES.fruit_abortion_probability, abs=0.02
    )
    young = [f for f in fruits if f.born_tt + TRUSSES.fruit_abortion_cd > FRUITING_CD]
    assert all(f.stage == FruitStage.ATTACHED for f in young)


def test_every_organ_keeps_its_identity_and_changes_stage_only_as_allowed() -> None:
    """Three of the lab's plants, day after day through the lab's run."""
    for plant_id in ("p01", "p02", "p03"):
        previous = plants.structure(0, plants.LAB_SEED, plant_id)
        for day in range(1, plants.LAST_DAY + 1):
            current = grow(previous, [plants.LAB_TEMPERATURE_C], plants.DEVELOPMENT)
            assert change_problems(previous, current) == [], (plant_id, day)
            assert topology_problems(current) == [], (plant_id, day)
            previous = current
        assert previous == plants.structure(plants.LAST_DAY, plants.LAB_SEED, plant_id)


def test_a_fruit_followed_from_its_set_keeps_its_identifier_and_birth() -> None:
    seen: dict[str, float] = {}
    for day in range(0, plants.LAST_DAY + 1, 5):
        fruits = {f.fruit_id: f.born_tt for f in _fruits(plants.structure(day))}
        assert seen.items() <= fruits.items()
        seen = fruits
    assert seen


def test_a_change_that_is_not_allowed_is_found_out() -> None:
    before = plants.structure(45)
    after = plants.structure(50)
    rank, truss = next((p.rank, p.truss) for p in after.stem.phytomers if p.truss is not None)
    assert truss is not None
    flower = next(f for f in truss.flowers if f.stage == FlowerStage.SET)
    back_to_bud = truss.model_copy(
        update={
            "flowers": tuple(
                f.model_copy(update={"stage": FlowerStage.BUD, "fruit": None})
                if f.flower_id == flower.flower_id
                else f
                for f in truss.flowers
            )
        }
    )
    unexpanded = after.stem.phytomers[0].leaf.model_copy(update={"stage": LeafStage.EXPANDING})
    reborn = after.stem.phytomers[1].model_copy(update={"born_tt": 1.0})

    assert change_problems(before, _with_stage(after, rank, {"truss": back_to_bud})) == [
        f"{flower.flower_id} went from set to bud",
        f"{flower.fruit.fruit_id if flower.fruit else ''} is gone",
    ]
    assert change_problems(before, _with_stage(after, 1, {"leaf": unexpanded})) == [
        "p01_n01_leaf went from mature to expanding"
    ]
    assert change_problems(before, _with_stage(after, 2, {"born_tt": reborn.born_tt})) == [
        "p01_n02 is not the organ it was"
    ]
    assert change_problems(after, before) != []
    assert "the plant's thermal time went back" in change_problems(after, before)


def test_a_plant_sets_the_same_fruit_grown_in_one_step_or_day_by_day() -> None:
    transplant = develop(emerged("p01", PARAMS, seed=4), plants.TRANSPLANT_CD, PARAMS)
    daily = grow(transplant, [21.0] * 60, PARAMS)

    assert daily == develop(transplant, 60 * 11.0, PARAMS)
    assert _fruits(daily)


def test_the_labs_first_plant_flowers_and_fruits_on_reference_days() -> None:
    def tally(day: int) -> tuple[int, dict[str, int], int]:
        plant = plants.structure(day)
        stages = Counter(flower.stage.value for flower in _flowers(plant))
        return len(_trusses(plant)), dict(sorted(stages.items())), len(_fruits(plant))

    assert tally(0) == (0, {}, 0)
    assert tally(30) == (4, {"aborted": 2, "bud": 7, "open": 5, "set": 2}, 2)
    assert tally(60) == (7, {"aborted": 6, "bud": 9, "open": 4, "set": 13}, 13)


def test_buds_flowers_and_fruits_are_drawn_as_they_are_and_dropped_ones_not() -> None:
    plant = plants.structure(60)
    shapes = {s.organ_id: s for s in organ_geometry(plant)}
    for truss in _trusses(plant):
        stick = shapes[truss.truss_id].shape
        assert isinstance(stick, Cylinder)
        assert stick.height == pytest.approx(FLOWER_SPACING_M * truss.final_flower_count)
        for flower in truss.flowers:
            fruit = flower.fruit
            drawn = shapes.get(flower.flower_id)
            if flower.stage in {FlowerStage.BUD, FlowerStage.OPEN}:
                assert drawn is not None and isinstance(drawn.shape, Sphere)
                radius = BUD_RADIUS_M if flower.stage == FlowerStage.BUD else FLOWER_RADIUS_M
                assert drawn.shape.radius == radius
            else:
                assert drawn is None
            if fruit is not None and fruit.stage == FruitStage.ATTACHED:
                sphere = shapes[fruit.fruit_id].shape
                assert isinstance(sphere, Sphere)
                assert sphere.radius == pytest.approx(fruit.diameter_mm * METRES_PER_MM / 2)
            elif fruit is not None:
                assert fruit.fruit_id not in shapes


def test_the_scene_colours_a_bud_green_and_an_open_flower_yellow() -> None:
    entities = plant_entities(plants.structure(60), Transform(position=Vector3(x=0, y=0, z=0)))
    flowers = [e for e in entities if e.kind == SceneEntityKind.FLOWER]
    fruits = [e for e in entities if e.kind == SceneEntityKind.FRUIT]

    assert {e.properties["stage"] for e in flowers} == {"bud", "open"}
    for entity in flowers:
        assert entity.color == (BUD_COLOR if entity.properties["stage"] == "bud" else FLOWER_COLOR)
    assert fruits and all(str(e.properties["parent_id"]).count("_fl") == 1 for e in fruits)


def test_a_truss_with_fewer_flowers_than_it_bears_is_found_out() -> None:
    with pytest.raises(ValidationError, match="min_flowers is more than max_flowers"):
        TrussParams(min_flowers=9)
    plant = plants.structure(30)
    rank, truss = next((p.rank, p.truss) for p in plant.stem.phytomers if p.truss is not None)
    assert truss is not None
    crowded = truss.model_copy(update={"final_flower_count": len(truss.flowers) - 1})

    assert topology_problems(_with_stage(plant, rank, {"truss": crowded})) == [
        f"{truss.truss_id} has more flowers than it bears"
    ]
