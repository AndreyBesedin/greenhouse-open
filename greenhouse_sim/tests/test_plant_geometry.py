"""A plant's geometry, derived from its organs' state: every dimension drawn
is one the organs or the plant's form give."""

import math

import pytest

from greenhouse_sim.biology.tomato.organ import reference
from greenhouse_sim.biology.tomato.organ.geometry import (
    GOLDEN_ANGLE_RAD,
    LEAFLET_THICKNESS_M,
    METRES_PER_CM,
    METRES_PER_MM,
    OrganShape,
    PlantForm,
    organ_geometry,
)
from greenhouse_sim.biology.tomato.organ.reference import young_plant
from greenhouse_sim.biology.tomato.organ.topology import Leaf, OrganKind, Plant
from greenhouse_sim.world.geometry import Cylinder, Ellipsoid, Sphere, Vector3

PLANT = young_plant("p01")
FORM = PlantForm()
X = Vector3(x=1.0, y=0.0, z=0.0)
Z = Vector3(x=0.0, y=0.0, z=1.0)


def _shapes(plant: Plant = PLANT, form: PlantForm = FORM) -> dict[str, OrganShape]:
    return {shape.shape_id: shape for shape in organ_geometry(plant, form)}


def _leaf(rank: int, plant: Plant = PLANT) -> Leaf:
    return plant.stem.phytomers[rank - 1].leaf


def _leaf_parts(organ_id: str, shapes: dict[str, OrganShape]) -> list[OrganShape]:
    return [shape for shape in shapes.values() if shape.organ_id == organ_id]


def _axis(shape: OrganShape, axis: Vector3) -> Vector3:
    """Where one of the shape's own axes points, in the plant's frame."""
    return shape.transform.rotation.rotate(axis)


def _end(shape: OrganShape) -> Vector3:
    """The far end of a cylinder, or of a leaflet from where it is attached."""
    if isinstance(shape.shape, Cylinder):
        return shape.transform.apply(Vector3(x=0.0, y=0.0, z=shape.shape.height))
    assert isinstance(shape.shape, Ellipsoid)
    return shape.transform.apply(Vector3(x=shape.shape.size_x / 2, y=0.0, z=0.0))


def _base(shape: OrganShape) -> Vector3:
    """Where a cylinder starts, or where a leaflet is attached."""
    if isinstance(shape.shape, Cylinder):
        return shape.transform.position
    assert isinstance(shape.shape, Ellipsoid)
    return shape.transform.apply(Vector3(x=-shape.shape.size_x / 2, y=0.0, z=0.0))


def _close(first: Vector3, second: Vector3) -> bool:
    return math.dist((first.x, first.y, first.z), (second.x, second.y, second.z)) < 1e-9


def _elevation(direction: Vector3) -> float:
    return math.atan2(direction.z, math.hypot(direction.x, direction.y))


def test_internodes_stack_up_the_stem_as_long_and_thick_as_they_are() -> None:
    shapes = [s for s in organ_geometry(PLANT) if s.kind == OrganKind.INTERNODE]
    internodes = [phytomer.internode for phytomer in PLANT.stem.phytomers]

    assert [s.organ_id for s in shapes] == [i.internode_id for i in internodes]
    assert shapes[0].transform.position == Vector3(x=0.0, y=0.0, z=0.0)
    for shape, internode in zip(shapes, internodes, strict=True):
        assert isinstance(shape.shape, Cylinder)
        assert shape.shape.height == pytest.approx(internode.length_cm * METRES_PER_CM)
        assert shape.shape.radius == pytest.approx(internode.diameter_mm * METRES_PER_MM / 2)
    for below, above in zip(shapes, shapes[1:], strict=False):
        assert _close(_end(below), above.transform.position)


def test_the_youngest_phytomers_are_still_growing() -> None:
    lengths = [phytomer.leaf.length_cm for phytomer in PLANT.stem.phytomers]
    diameters = [phytomer.internode.diameter_mm for phytomer in PLANT.stem.phytomers]
    growing = reference.MATURE_BELOW

    assert lengths[:-growing] == [reference.LEAF_LENGTH_CM] * (len(lengths) - growing)
    assert lengths[-growing:] == sorted(lengths[-growing:], reverse=True)
    assert lengths[-1] < reference.LEAF_LENGTH_CM / 2
    assert diameters == sorted(diameters, reverse=True)


def test_a_leaf_is_a_petiole_a_rachis_and_its_leaflets_joined_end_to_end() -> None:
    shapes = _shapes()
    leaf = "p01_n04_leaf"
    pairs = FORM.leaflet_pairs
    names = [s.shape_id.removeprefix(f"{leaf}_") for s in _leaf_parts(leaf, shapes)]

    assert names == [
        "petiole",
        "leaflet1_left",
        "leaflet1_right",
        "rachis1",
        "leaflet2_left",
        "leaflet2_right",
        "rachis2",
        "leaflet3_left",
        "leaflet3_right",
        "rachis3",
        "terminal",
    ]
    stalk = [shapes[f"{leaf}_petiole"]] + [shapes[f"{leaf}_rachis{n}"] for n in range(1, pairs + 1)]
    node = _end(shapes["p01_n04_internode"])
    assert _close(stalk[0].transform.position, node)
    for before, after in zip(stalk, stalk[1:], strict=False):
        assert _close(_end(before), after.transform.position)
    # Each pair where one segment meets the next, the terminal leaflet at the tip.
    for pair, segment in enumerate(stalk[:-1], start=1):
        for side in ("left", "right"):
            assert _close(_base(shapes[f"{leaf}_leaflet{pair}_{side}"]), _end(segment))
    assert _close(_base(shapes[f"{leaf}_terminal"]), _end(stalk[-1]))


def test_a_leaf_reaches_as_far_as_it_is_long() -> None:
    shapes = _shapes()
    for rank in (2, 8, 9):
        leaf = _leaf(rank)
        parts = _leaf_parts(leaf.leaf_id, shapes)
        stalk = sum(s.shape.height for s in parts if isinstance(s.shape, Cylinder))
        terminal = shapes[f"{leaf.leaf_id}_terminal"].shape
        assert isinstance(terminal, Ellipsoid)

        assert stalk + terminal.size_x == pytest.approx(leaf.length_cm * METRES_PER_CM)
        assert terminal.size_x == pytest.approx(
            leaf.length_cm * METRES_PER_CM * FORM.terminal_leaflet_fraction
        )


def test_leaflets_are_sized_by_their_leaf_and_grow_towards_its_tip() -> None:
    shapes = _shapes()
    leaf = "p01_n03_leaf"
    names = [f"leaflet{pair}_left" for pair in range(1, FORM.leaflet_pairs + 1)] + ["terminal"]
    leaflets = [shapes[f"{leaf}_{name}"].shape for name in names]
    assert all(isinstance(shape, Ellipsoid) for shape in leaflets)
    sizes = [shape.size_x for shape in leaflets if isinstance(shape, Ellipsoid)]

    assert sizes == sorted(sizes) and len(set(sizes)) == len(sizes)
    assert sizes[0] == pytest.approx(sizes[-1] * FORM.basal_leaflet_scale)
    for shape in leaflets:
        assert isinstance(shape, Ellipsoid)
        assert shape.size_y == pytest.approx(shape.size_x * FORM.leaflet_aspect)
        assert shape.size_z == LEAFLET_THICKNESS_M
    left, right = shapes[f"{leaf}_leaflet2_left"], shapes[f"{leaf}_leaflet2_right"]
    assert left.shape == right.shape


def test_a_pair_of_leaflets_spreads_either_side_of_the_rachis_lying_in_the_leaf() -> None:
    shapes = _shapes()
    leaf = "p01_n05_leaf"
    rachis = _axis(shapes[f"{leaf}_rachis1"], Z)
    left, right = shapes[f"{leaf}_leaflet2_left"], shapes[f"{leaf}_leaflet2_right"]
    across = rachis.cross(_axis(left, Z))

    for leaflet, side in ((left, 1), (right, -1)):
        along = _axis(leaflet, X)
        spread = math.acos(rachis.x * along.x + rachis.y * along.y + rachis.z * along.z)
        assert spread == pytest.approx(FORM.leaflet_angle_rad)
        assert side * (along.x * across.x + along.y * across.y + along.z * across.z) < 0
        # Flat in the leaf's plane, which holds the rachis: its face is square to it.
        normal = _axis(leaflet, Z)
        assert normal.x * rachis.x + normal.y * rachis.y + normal.z * rachis.z == pytest.approx(0)
        assert normal.z > 0


def test_a_leaf_rises_from_its_node_and_bends_down_the_more_the_longer_it_is() -> None:
    shapes = _shapes()

    def bend(rank: int) -> float:
        leaf = _leaf(rank).leaf_id
        petiole = _elevation(_axis(shapes[f"{leaf}_petiole"], Z))
        tip = _elevation(_axis(shapes[f"{leaf}_terminal"], X))
        assert petiole == pytest.approx(FORM.leaf_insertion_rad)
        return petiole - tip

    full, growing = bend(2), bend(9)
    assert full == pytest.approx(
        FORM.full_leaf_droop_rad * reference.LEAF_LENGTH_CM / FORM.full_leaf_length_cm
    )
    assert growing == pytest.approx(full * _leaf(9).length_cm / _leaf(2).length_cm)
    # Each segment bent further down than the last.
    leaf = _leaf(2).leaf_id
    stalk = ["petiole"] + [f"rachis{n}" for n in range(1, FORM.leaflet_pairs + 1)]
    rises = [_elevation(_axis(shapes[f"{leaf}_{name}"], Z)) for name in stalk]
    assert rises == sorted(rises, reverse=True)


def test_successive_leaves_turn_about_the_stem_by_the_golden_angle() -> None:
    shapes = _shapes()
    azimuths = []
    for phytomer in PLANT.stem.phytomers:
        petiole = _axis(shapes[f"{phytomer.leaf.leaf_id}_petiole"], Z)
        azimuths.append(math.atan2(petiole.y, petiole.x))

    for before, after in zip(azimuths, azimuths[1:], strict=False):
        turn = (after - before) % (2 * math.pi)
        assert turn == pytest.approx(GOLDEN_ANGLE_RAD)


def test_a_longer_leaf_is_drawn_longer_in_every_part() -> None:
    leaf = _leaf(9)
    longer = leaf.model_copy(update={"length_cm": leaf.length_cm * 2})
    *lower, youngest = PLANT.stem.phytomers
    phytomers = (*lower, youngest.model_copy(update={"leaf": longer}))
    stem = PLANT.stem.model_copy(update={"phytomers": phytomers})
    grown = PLANT.model_copy(update={"stem": stem})
    before, after = _leaf_parts(leaf.leaf_id, _shapes()), _leaf_parts(leaf.leaf_id, _shapes(grown))

    def length(shape: OrganShape) -> float:
        assert isinstance(shape.shape, Cylinder | Ellipsoid)
        return shape.shape.height if isinstance(shape.shape, Cylinder) else shape.shape.size_x

    assert [s.shape_id for s in after] == [s.shape_id for s in before]
    for old, new in zip(before, after, strict=True):
        assert length(new) == pytest.approx(2 * length(old))


def test_the_plants_form_shapes_its_leaves() -> None:
    form = PlantForm(leaflet_pairs=4, leaflet_aspect=0.3)
    shapes = _shapes(form=form)
    parts = _leaf_parts("p01_n02_leaf", shapes)
    leaflets = [s.shape for s in parts if s.part == "leaflet"]

    assert len(leaflets) == 2 * 4 + 1
    assert sum(s.part == "rachis" for s in parts) == 4
    for leaflet in leaflets:
        assert isinstance(leaflet, Ellipsoid)
        assert leaflet.size_y == pytest.approx(leaflet.size_x * 0.3)


def test_a_trusss_flowers_hang_along_it() -> None:
    shapes = _shapes()
    flowers = [shapes[f"p01_t01_fl{rank:02d}"] for rank in range(1, 7)]

    assert all(isinstance(f.shape, Sphere) and f.kind == OrganKind.FLOWER for f in flowers)
    # Further from the stem, and lower, the further along the truss.
    reach = [math.hypot(f.transform.position.x, f.transform.position.y) for f in flowers]
    assert reach == sorted(reach)


def test_every_shape_is_a_part_of_an_organ_of_the_plant() -> None:
    organs = {organ_id: kind for kind, organ_id, _, _ in PLANT.organs()}
    shapes = organ_geometry(PLANT)
    parts = {
        OrganKind.INTERNODE: {"internode"},
        OrganKind.LEAF: {"petiole", "rachis", "leaflet"},
        OrganKind.TRUSS: {"truss"},
        OrganKind.FLOWER: {"flower"},
        OrganKind.FRUIT: {"fruit"},
    }

    assert len({s.shape_id for s in shapes}) == len(shapes)
    for shape in shapes:
        assert organs[shape.organ_id] == shape.kind
        assert shape.part in parts[shape.kind]
