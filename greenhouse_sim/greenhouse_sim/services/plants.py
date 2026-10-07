"""The plant lab: tomato plants from the organ-level model, to look at.

A client asks for a plant's structure, organ by organ, and for the scene a
viewer draws of it: the plant on a patch of ground, every organ an entity
that says which organ it is, on any day of the lab's run. The lab's plant is
a transplant, grown by the development model at a constant temperature from
day 0 to `LAST_DAY`.
"""

from typing import Final

from greenhouse_sim.biology.tomato.organ.development import (
    DevelopmentParams,
    develop,
    emerged,
    grow,
)
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
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.world.geometry import Axes, Plane, Transform, Vector3

LAB_ID: Final = "plant_lab"
LAB_PLANT_ID: Final = "p01"
# The lab's patch of ground around its plants.
GROUND_SIZE_M: Final = 3.0
GROUND_COLOR: Final = Color(r=0.45, g=0.36, b=0.27)
# The lab's plant is a transplant this far into its development on day 0,
# kept at this daily mean temperature, and shown up to this day.
TRANSPLANT_CD: Final = 230.0
LAB_TEMPERATURE_C: Final = 21.0
LAST_DAY: Final = 60
DEVELOPMENT: Final = DevelopmentParams()

_ORIGIN: Final = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))


def structure(day: int = 0) -> Plant:
    """The lab's plant on this day, organ by organ."""
    if not 0 <= day <= LAST_DAY:
        raise InvalidRequest(f"the plant lab runs from day 0 to day {LAST_DAY}, not day {day}")
    transplant = develop(emerged(LAB_PLANT_ID, DEVELOPMENT), TRANSPLANT_CD, DEVELOPMENT)
    return grow(transplant, [LAB_TEMPERATURE_C] * day, DEVELOPMENT)


def scene(day: int = 0) -> SceneSnapshot:
    """The lab's plant on this day, on its ground, as a viewer draws it."""
    plant = structure(day)
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
        simulated_day=day,
        entities=[ground, *plant_entities(plant, _ORIGIN), axes],
    )
