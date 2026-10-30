"""A crop grown by area drawn as what it is (decision 0062): a canopy over
each scope, a see-through volume along its planting positions and as wide
as its cultivated area, marked as a proxy and its numbers as predictions,
never plants it does not have.
"""

from typing import Final

import pytest

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SceneEntityKind, canopy_entity
from greenhouse_sim.world.geometry import Box
from greenhouse_sim.world.scopes import row_scopes

CANOPY_M: Final = 1.8
DENSITY: Final = 0.4


@pytest.mark.parametrize("scenario_id", ["reference_greenhouse", "climate_box"])
def test_a_canopy_stands_over_its_scopes_ground(scenario_id: str) -> None:
    config = SCENARIO_REGISTRY[scenario_id]
    for scope in row_scopes(config.layout, config.envelope):
        canopy = canopy_entity(
            scope,
            config.envelope,
            entity_id=f"{scope.scope_id}_canopy",
            height_m=CANOPY_M,
            density=DENSITY,
            properties={"lai": 1.5},
        )
        box = canopy.shape
        assert isinstance(box, Box)

        assert canopy.kind == SceneEntityKind.CANOPY
        # As wide as its cultivated area, as tall as its canopy.
        assert box.size_x * box.size_y == pytest.approx(scope.cultivated_m2, rel=1e-12)
        assert box.size_z == CANOPY_M
        # Every planting position under it, on its base.
        centre = canopy.transform.position
        for position in scope.positions:
            point = config.envelope.to_world(position.point)
            assert abs(point.x - centre.x) < box.size_x / 2
            assert abs(point.y - centre.y) < box.size_y / 2
            assert point.z == pytest.approx(centre.z, abs=1e-12)
        assert canopy.properties == {
            "scope": scope.scope_id,
            "proxy": True,
            "prediction": True,
            "density": DENSITY,
            "height_m": CANOPY_M,
            "lai": 1.5,
        }
        assert canopy.label == f"{scope.scope_id} canopy (a proxy)"
