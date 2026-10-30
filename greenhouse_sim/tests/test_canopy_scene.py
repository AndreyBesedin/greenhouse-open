"""A crop grown by area drawn as what it is (decision 0062): a canopy over
each scope, a see-through volume over each unbroken run of its row's
planting positions, as wide as the row's share of the ground, marked as a
proxy and its numbers as predictions, never plants it does not have.
"""

import itertools
import math
from typing import Final

import pytest

from greenhouse_sim.domain.layout import ZoneKind
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scene.snapshot import SceneEntity, SceneEntityKind, canopy_entities
from greenhouse_sim.world.geometry import Box, Point2, Quaternion, Vector3
from greenhouse_sim.world.scopes import row_scopes
from greenhouse_sim.world.zones import Strip, Zone

CANOPY_M: Final = 1.8
DENSITY: Final = 0.4
# How near a planting position may lie to its canopy's edge, along its row:
# half a pitch in, as each position stands in the middle of its own.
EDGE_M: Final = 1e-9
REFERENCE: Final = SCENARIO_REGISTRY["reference_greenhouse"]


def _reference_with(**rows: object) -> ScenarioConfig:
    """The reference greenhouse, its crop rows changed so."""
    layout = REFERENCE.layout
    assert layout.crop_rows is not None
    changed = layout.crop_rows.model_copy(update=rows)
    return REFERENCE.model_copy(update={"layout": layout.model_copy(update={"crop_rows": changed})})


def _with_a_gap() -> ScenarioConfig:
    """The reference greenhouse, a service zone across its first row's
    middle positions, so that the row grows in two runs."""
    rows = REFERENCE.layout.crop_rows
    assert rows is not None
    zone = Zone(
        zone_id="cart_crossing",
        kind=ZoneKind.SERVICE,
        area=Strip(
            start=Point2(**rows.point(1, 3.5 * rows.plant_pitch).model_dump(exclude={"z"})),
            end=Point2(
                **rows.point(1, 3.5 * rows.plant_pitch, across=0.1).model_dump(exclude={"z"})
            ),
            width=rows.plant_pitch,
        ),
        height=1.0,
    )
    layout = REFERENCE.layout.model_copy(update={"zones": [*REFERENCE.layout.zones, zone]})
    return REFERENCE.model_copy(update={"layout": layout})


LAYOUTS: Final = {
    "as it is": REFERENCE,
    "its rows turned 20°": _reference_with(heading=math.radians(20)),
    "paired rows": _reference_with(pair_gap=0.5),
    "a row in two runs": _with_a_gap(),
    "a row of one position": SCENARIO_REGISTRY["sensor_lab"],
    "the climate box": SCENARIO_REGISTRY["climate_box"],
}


def _canopies(config: ScenarioConfig) -> dict[str, list[SceneEntity]]:
    return {
        scope.scope_id: canopy_entities(
            scope,
            config.layout,
            config.envelope,
            entity_id=f"{scope.scope_id}_canopy",
            height_m=CANOPY_M,
            density=DENSITY,
            properties={"lai": 1.5, "proxy": False, "density": 9.0},
        )
        for scope in row_scopes(config.layout, config.envelope)
    }


def _in_the_box(canopy: SceneEntity, point: Vector3) -> Vector3:
    """`point`, in the world, as its canopy's box frame has it."""
    turn = canopy.transform.rotation
    back = Quaternion(w=turn.w, x=-turn.x, y=-turn.y, z=-turn.z)
    offset = point.model_dump()
    centre = canopy.transform.position.model_dump()
    return back.rotate(Vector3(**{axis: offset[axis] - centre[axis] for axis in "xyz"}))


@pytest.mark.parametrize("name", LAYOUTS)
def test_a_canopy_stands_over_every_planting_position_of_its_scope(name: str) -> None:
    config = LAYOUTS[name]
    canopies = _canopies(config)
    for scope in row_scopes(config.layout, config.envelope):
        drawn = canopies[scope.scope_id]
        boxes = [canopy.shape for canopy in drawn]
        assert all(isinstance(box, Box) for box in boxes)

        # Its volumes cover its cultivated area, each as tall as its canopy.
        footprint = sum(box.size_x * box.size_y for box in boxes if isinstance(box, Box))
        assert footprint == pytest.approx(scope.cultivated_m2, rel=1e-12)
        assert {canopy.kind for canopy in drawn} == {SceneEntityKind.CANOPY}
        # Each planting position under exactly one of them, on its base.
        for position in scope.positions:
            point = config.envelope.to_world(position.point)
            under = []
            for canopy, box in zip(drawn, boxes, strict=True):
                assert isinstance(box, Box)
                local = _in_the_box(canopy, point)
                if (
                    abs(local.x) < box.size_x / 2 - EDGE_M
                    and abs(local.y) < box.size_y / 2 - EDGE_M
                ):
                    under.append(canopy.entity_id)
                    assert local.z == pytest.approx(0.0, abs=1e-12)
            assert len(under) == 1, (position.position_id, under)
        # Marked as a proxy, whatever the model's own properties say.
        for canopy in drawn:
            assert canopy.properties["proxy"] is True
            assert canopy.properties["prediction"] is True
            assert canopy.properties["density"] == DENSITY
            assert canopy.properties["lai"] == 1.5
            assert canopy.label == f"{scope.scope_id} canopy (a proxy)"


def test_a_row_in_runs_is_drawn_one_volume_a_run() -> None:
    first_row = _canopies(LAYOUTS["a row in two runs"])["row_1"]

    assert [canopy.entity_id for canopy in first_row] == ["row_1_canopy_1", "row_1_canopy_2"]


@pytest.mark.parametrize("name", ["as it is", "paired rows", "its rows turned 20°"])
def test_the_canopies_of_two_rows_meet_without_overlapping(name: str) -> None:
    """Each row's share of the ground, across the rows: those of a pair
    meet halfway between its rows."""
    config = LAYOUTS[name]
    rows = config.layout.crop_rows
    assert rows is not None
    bands = []
    for drawn in _canopies(config).values():
        canopy = drawn[0]
        box = canopy.shape
        assert isinstance(box, Box)
        # Across the rows, from the first row's line, in the first canopy's frame.
        middle = _in_the_box(_canopies(config)["row_1"][0], canopy.transform.position).y
        bands.append((middle - box.size_y / 2, middle + box.size_y / 2))
    bands.sort()
    for (_, ends), (starts, _) in itertools.pairwise(bands):
        assert starts >= ends - 1e-9
    if rows.pair_gap is not None:
        # A pair's two shares meet: one band's end is the next one's start.
        assert bands[1][0] == pytest.approx(bands[0][1], abs=1e-9)
