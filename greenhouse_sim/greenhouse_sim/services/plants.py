"""The plant lab: tomato plants from the organ-level model, to look at.

A client asks for a plant's structure, organ by organ, and for the scene a
viewer draws of it: the plant on a patch of ground, every organ an entity
that says which organ it is. P03 grows the lab with the model: today it
shows the reference young plant (P03.1).
"""

from typing import Final

from greenhouse_sim.biology.tomato.organ.reference import young_plant
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.scene.plants import plant_entities
from greenhouse_sim.scene.snapshot import (
    AXES_COLOR,
    AXES_LENGTH_M,
    Color,
    SceneEntity,
    SceneEntityKind,
    SceneSnapshot,
)
from greenhouse_sim.world.geometry import Axes, Plane, Transform, Vector3

LAB_ID: Final = "plant_lab"
LAB_PLANT_ID: Final = "p01"
# The lab's patch of ground around its plants.
GROUND_SIZE_M: Final = 3.0
GROUND_COLOR: Final = Color(r=0.45, g=0.36, b=0.27)

_ORIGIN: Final = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))


def structure() -> Plant:
    """The lab's plant, organ by organ."""
    return young_plant(LAB_PLANT_ID)


def scene() -> SceneSnapshot:
    """The lab's plant on its ground, as a viewer draws it."""
    ground = SceneEntity(
        entity_id=f"{LAB_ID}_ground",
        kind=SceneEntityKind.GROUND,
        transform=_ORIGIN,
        shape=Plane(size_x=GROUND_SIZE_M, size_y=GROUND_SIZE_M),
        color=GROUND_COLOR,
        label="ground",
    )
    axes = SceneEntity(
        entity_id=f"{LAB_ID}_axes",
        kind=SceneEntityKind.AXES,
        transform=_ORIGIN,
        shape=Axes(length=AXES_LENGTH_M),
        color=AXES_COLOR,
        label="world axes",
    )
    return SceneSnapshot(
        greenhouse_id=LAB_ID,
        simulated_day=0,
        entities=[ground, *plant_entities(structure(), _ORIGIN), axes],
    )
