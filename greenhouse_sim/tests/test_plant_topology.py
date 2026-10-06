"""The organ-level tomato model's structure: organs, identities, the seed
hierarchy, the geometry derived from them, and the plant lab that shows
them."""

import math
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.tomato.organ import reference
from greenhouse_sim.biology.tomato.organ.geometry import (
    LEAF_STICK_RADIUS_M,
    METRES_PER_CM,
    organ_geometry,
)
from greenhouse_sim.biology.tomato.organ.reference import young_plant
from greenhouse_sim.biology.tomato.organ.seeds import organ_rng, plant_rng
from greenhouse_sim.biology.tomato.organ.topology import (
    Flower,
    FlowerStage,
    Fruit,
    OrganKind,
    Plant,
    topology_problems,
)
from greenhouse_sim.scene.plants import plant_entities
from greenhouse_sim.scene.snapshot import SceneEntityKind, SceneSnapshot
from greenhouse_sim.services import plants
from greenhouse_sim.world.geometry import Cylinder, Sphere, Transform, Vector3

PLANT = young_plant("p01")


def test_the_reference_plant_keeps_every_rule_of_the_structure() -> None:
    assert topology_problems(PLANT) == []


def test_organs_are_named_by_where_they_sit() -> None:
    ids = [organ_id for _, organ_id, _, _ in PLANT.organs()]

    assert ids[:5] == ["p01", "p01_stem", "p01_n01", "p01_n01_internode", "p01_n01_leaf"]
    assert {"p01_n09_leaf", "p01_t01", "p01_t01_fl01", "p01_t01_fl06"} <= set(ids)


def test_every_organ_names_its_parent() -> None:
    parents = {organ_id: parent for _, organ_id, parent, _ in PLANT.organs()}

    assert parents["p01"] is None
    assert parents["p01_stem"] == "p01"
    assert parents["p01_n05"] == "p01_stem"
    assert parents["p01_n05_leaf"] == "p01_n05"
    assert parents["p01_t01"] == "p01_n09"
    assert parents["p01_t01_fl03"] == "p01_t01"


def test_identifiers_are_the_same_on_every_build() -> None:
    assert young_plant("p01") == PLANT
    assert young_plant("p02").stem.phytomers[0].phytomer_id == "p02_n01"


def test_an_organs_thermal_age_is_the_thermal_time_since_it_appeared() -> None:
    youngest, oldest = PLANT.stem.phytomers[-1], PLANT.stem.phytomers[0]

    assert PLANT.thermal_age(youngest) == 0.0
    assert PLANT.thermal_age(oldest) == (reference.PHYTOMERS - 1) * reference.PHYLLOCHRON_CD


def _with_flower(plant: Plant, flower: Flower) -> Plant:
    """The plant with its first truss's first flower replaced."""
    phytomers = list(plant.stem.phytomers)
    rank = reference.FIRST_TRUSS_RANK
    phytomer = phytomers[rank - 1]
    assert phytomer.truss is not None
    flowers = (flower, *phytomer.truss.flowers[1:])
    phytomers[rank - 1] = phytomer.model_copy(
        update={"truss": phytomer.truss.model_copy(update={"flowers": flowers})}
    )
    return plant.model_copy(
        update={"stem": plant.stem.model_copy(update={"phytomers": tuple(phytomers)})}
    )


def _first_flower(plant: Plant) -> Flower:
    truss = plant.stem.phytomers[reference.FIRST_TRUSS_RANK - 1].truss
    assert truss is not None
    return truss.flowers[0]


@pytest.mark.parametrize(
    ("broken", "problem"),
    [
        # A fruit on a flower that did not set.
        (
            _with_flower(
                PLANT,
                _first_flower(PLANT).model_copy(
                    update={"fruit": Fruit(fruit_id="p01_t01_fr01", born_tt=264.0, diameter_mm=2.0)}
                ),
            ),
            "has a fruit if and only if it set",
        ),
        # A set flower without its fruit.
        (
            _with_flower(PLANT, _first_flower(PLANT).model_copy(update={"stage": FlowerStage.SET})),
            "has a fruit if and only if it set",
        ),
        # A fruit that does not take its flower's place.
        (
            _with_flower(
                PLANT,
                _first_flower(PLANT).model_copy(
                    update={
                        "stage": FlowerStage.SET,
                        "fruit": Fruit(fruit_id="p01_t01_fr09", born_tt=264.0, diameter_mm=2.0),
                    }
                ),
            ),
            "should take its flower's place",
        ),
        # A flower that appears after the plant's thermal time.
        (
            _with_flower(PLANT, _first_flower(PLANT).model_copy(update={"born_tt": 1000.0})),
            "appeared after the plant's thermal time",
        ),
        # A flower named for another place.
        (
            _with_flower(
                PLANT, _first_flower(PLANT).model_copy(update={"flower_id": "p01_t01_fl07"})
            ),
            "should be p01_t01_fl01",
        ),
    ],
)
def test_a_structure_that_breaks_a_rule_is_found_out(broken: Plant, problem: str) -> None:
    problems = topology_problems(broken)

    assert any(problem in found for found in problems), problems


def test_phytomers_out_of_order_or_repeated_are_found_out() -> None:
    phytomers = PLANT.stem.phytomers
    swapped = (phytomers[1], phytomers[0], *phytomers[2:])
    repeated = (phytomers[0], phytomers[0], *phytomers[2:])

    def problems(stack: tuple[object, ...]) -> list[str]:
        stem = PLANT.stem.model_copy(update={"phytomers": stack})
        return topology_problems(PLANT.model_copy(update={"stem": stem}))

    assert any("has rank 2, not 1" in found for found in problems(swapped))
    assert any("identifiers used twice" in found for found in problems(repeated))


def test_draws_follow_the_seed_hierarchy() -> None:
    vigour = plant_rng(7, "p01", "vigour").uniform()

    assert plant_rng(7, "p01", "vigour").uniform() == vigour
    assert plant_rng(8, "p01", "vigour").uniform() != vigour
    assert plant_rng(7, "p02", "vigour").uniform() != vigour
    assert plant_rng(7, "p01", "phyllochron").uniform() != vigour
    fruit_set = organ_rng(7, "p01", "p01_t01_fl01", "fruit_set").uniform()
    assert organ_rng(7, "p01", "p01_t01_fl01", "fruit_set").uniform() == fruit_set
    assert organ_rng(7, "p01", "p01_t01_fl02", "fruit_set").uniform() != fruit_set


def _top(shape: Cylinder, transform: Transform) -> Vector3:
    return transform.apply(Vector3(x=0.0, y=0.0, z=shape.height))


def test_internodes_stack_up_the_stem_at_their_lengths() -> None:
    shapes = [s for s in organ_geometry(PLANT) if s.kind == OrganKind.INTERNODE]
    length_m = reference.INTERNODE_LENGTH_CM * METRES_PER_CM

    assert [s.organ_id for s in shapes] == [f"p01_n{rank:02d}_internode" for rank in range(1, 10)]
    for below, above in zip(shapes, shapes[1:], strict=False):
        assert isinstance(below.shape, Cylinder)
        assert _top(below.shape, below.transform).z == pytest.approx(above.transform.position.z)
        assert below.shape.height == pytest.approx(length_m)


def test_each_leaf_reaches_from_its_node_as_long_as_the_leaf() -> None:
    shapes = {s.organ_id: s for s in organ_geometry(PLANT)}
    leaf, internode = shapes["p01_n04_leaf"], shapes["p01_n04_internode"]
    assert isinstance(leaf.shape, Cylinder) and isinstance(internode.shape, Cylinder)
    node = _top(internode.shape, internode.transform)

    assert leaf.shape.height == pytest.approx(reference.LEAF_LENGTH_CM * METRES_PER_CM)
    assert leaf.shape.radius == LEAF_STICK_RADIUS_M
    assert leaf.transform.position == node
    tip = _top(leaf.shape, leaf.transform)
    assert math.hypot(tip.x, tip.y) > 0 and tip.z > node.z


def test_a_trusss_flowers_hang_along_it() -> None:
    shapes = {s.organ_id: s for s in organ_geometry(PLANT)}
    flowers = [shapes[f"p01_t01_fl{rank:02d}"] for rank in range(1, 7)]

    assert all(isinstance(f.shape, Sphere) and f.kind == OrganKind.FLOWER for f in flowers)
    # Further from the stem, and lower, the further along the truss.
    reach = [math.hypot(f.transform.position.x, f.transform.position.y) for f in flowers]
    assert reach == sorted(reach)


def test_every_shape_belongs_to_an_organ_of_the_plant() -> None:
    organs = {organ_id for _, organ_id, _, _ in PLANT.organs()}
    shapes = organ_geometry(PLANT)

    assert {s.organ_id for s in shapes} <= organs
    assert len({s.shape_id for s in shapes}) == len(shapes)


def test_the_scene_draws_each_organ_where_the_plant_stands_and_says_what_it_is() -> None:
    at = Transform(position=Vector3(x=2.0, y=1.0, z=0.5))
    entities = {e.entity_id: e for e in plant_entities(PLANT, at)}
    first = entities["p01_n01_internode"]
    flower = entities["p01_t01_fl02"]

    assert first.kind == SceneEntityKind.INTERNODE
    assert first.transform.position == Vector3(x=2.0, y=1.0, z=0.5)
    assert flower.kind == SceneEntityKind.FLOWER
    assert flower.properties["parent_id"] == "p01_t01"
    assert flower.properties["organ_kind"] == "flower"
    assert flower.properties["stage"] == "bud"
    assert first.properties["thermal_age_cd"] == pytest.approx(264.0)


def test_the_plant_lab_answers_with_its_scene_and_structure() -> None:
    scene, structure = respond("GET", "/api/plants/scene"), respond("GET", "/api/plants/structure")

    assert scene.status == structure.status == HTTPStatus.OK
    assert Plant.model_validate(structure.body) == plants.structure()
    kinds = {entity.kind for entity in SceneSnapshot.model_validate(scene.body).entities}
    assert {"GROUND", "INTERNODE", "LEAF", "TRUSS", "FLOWER"} <= kinds
