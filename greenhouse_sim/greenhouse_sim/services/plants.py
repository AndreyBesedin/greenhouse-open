"""The plant lab: tomato plants from the organ-level model, to look at.

A client asks for a plant's structure, organ by organ, and for the scene a
viewer draws of the lab: its row of plants on a patch of ground, every organ
an entity that says which organ, and which plant, it is. The lab's plants are
transplants of one crop, each with traits drawn from the lab's seed, grown by
the development model at a constant temperature from day 0 to `LAST_DAY`. The
same seed gives the same row on every run; another seed, another row.
"""

from typing import Final

from greenhouse_sim.biology.tomato.organ.development import (
    DevelopmentParams,
    develop,
    emerged,
    grow,
)
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.biology.tomato.organ.variation import VariationParams, draw_traits
from greenhouse_sim.scene.plants import plant_entities
from greenhouse_sim.scene.snapshot import (
    AXES_COLOR,
    AXES_LENGTH_M,
    Color,
    SceneEntity,
    SceneEntityKind,
    SceneSnapshot,
)
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.world.geometry import Axes, Plane, Transform, Vector3

LAB_ID: Final = "plant_lab"
# The lab's row: this many plants, this far apart along +y from the origin.
ROW_PLANTS: Final = 20
PLANT_SPACING_M: Final = 0.5
# The plant a client is shown first, at the row's start.
LAB_PLANT_ID: Final = "p01"
# The seed a client is shown first.
LAB_SEED: Final = 1
# The lab's ground reaches this far beyond its row on every side.
GROUND_MARGIN_M: Final = 1.5
GROUND_COLOR: Final = Color(r=0.45, g=0.36, b=0.27)
# The lab's plants are transplants this far into their development on day 0,
# kept at this daily mean temperature, and shown up to this day.
TRANSPLANT_CD: Final = 230.0
LAB_TEMPERATURE_C: Final = 21.0
LAST_DAY: Final = 90
# The crop: how its plants develop, their organs varying around each plant's
# sizes, and how its plants vary.
DEVELOPMENT: Final = DevelopmentParams(organ_size_cv=0.08)
VARIATION: Final = VariationParams()

_ORIGIN: Final = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))


def plant_ids() -> list[str]:
    """The row's plants, from its start."""
    return [f"p{place:02d}" for place in range(1, ROW_PLANTS + 1)]


def _checked(day: int, seed: int) -> None:
    if not 0 <= day <= LAST_DAY:
        raise InvalidRequest(f"the plant lab runs from day 0 to day {LAST_DAY}, not day {day}")
    if seed < 0:
        raise InvalidRequest(f"a seed is a whole number from 0, not {seed}")


def _grown(plant_id: str, day: int, seed: int) -> Plant:
    traits = draw_traits(seed, plant_id, VARIATION)
    transplant = develop(emerged(plant_id, DEVELOPMENT, seed, traits), TRANSPLANT_CD, DEVELOPMENT)
    return grow(transplant, [LAB_TEMPERATURE_C] * day, DEVELOPMENT)


def structure(day: int = 0, seed: int = LAB_SEED, plant_id: str = LAB_PLANT_ID) -> Plant:
    """One of the lab's plants on this day, organ by organ."""
    _checked(day, seed)
    if plant_id not in plant_ids():
        raise NotFound(f"the plant lab has no plant {plant_id!r}")
    return _grown(plant_id, day, seed)


def scene(day: int = 0, seed: int = LAB_SEED) -> SceneSnapshot:
    """The lab's row on this day, on its ground, as a viewer draws it."""
    _checked(day, seed)
    row_length = (ROW_PLANTS - 1) * PLANT_SPACING_M
    ground = SceneEntity(
        entity_id=f"{LAB_ID}_ground",
        kind=SceneEntityKind.GROUND,
        transform=Transform(position=Vector3(x=0.0, y=row_length / 2, z=0.0)),
        shape=Plane(size_x=2 * GROUND_MARGIN_M, size_y=row_length + 2 * GROUND_MARGIN_M),
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
    plants = [
        entity
        for place, plant_id in enumerate(plant_ids())
        for entity in plant_entities(
            _grown(plant_id, day, seed),
            Transform(position=Vector3(x=0.0, y=place * PLANT_SPACING_M, z=0.0)),
        )
    ]
    return SceneSnapshot(greenhouse_id=LAB_ID, simulated_day=day, entities=[ground, *plants, axes])
