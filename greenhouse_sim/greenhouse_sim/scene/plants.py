"""Plants organ by organ, as a viewer draws them.

Each shape of a plant's geometry (`greenhouse_sim.biology.tomato.organ.geometry`)
becomes an entity of its organ's kind, placed where the plant stands. Its
properties say which organ it is and which part of it, where that organ sits
in the plant, how far it has developed and how large it is, so a viewer can
inspect any organ and rebuild the plant's structure from what it draws. A
fruit's colour is its ripeness's: green, through yellow and orange, to red.
"""

from collections.abc import Mapping
from typing import Final

from greenhouse_sim.biology.tomato.organ.fruit import maturity
from greenhouse_sim.biology.tomato.organ.geometry import OrganShape, organ_geometry
from greenhouse_sim.biology.tomato.organ.topology import (
    FlowerStage,
    Fruit,
    Organ,
    OrganKind,
    Plant,
)
from greenhouse_sim.scene.snapshot import Color, SceneEntity, SceneEntityKind
from greenhouse_sim.world.geometry import Transform

STEM_COLOR: Final = Color(r=0.36, g=0.56, b=0.24)
LEAF_COLOR: Final = Color(r=0.18, g=0.5, b=0.2)
# A leaf's petiole and rachis are paler than its leaflets.
RACHIS_COLOR: Final = Color(r=0.4, g=0.62, b=0.26)
TRUSS_COLOR: Final = Color(r=0.42, g=0.6, b=0.28)
FLOWER_COLOR: Final = Color(r=0.96, g=0.84, b=0.18)
# A bud is still green, turning yellow as it opens.
BUD_COLOR: Final = Color(r=0.62, g=0.72, b=0.24)
FRUIT_COLOR: Final = Color(r=0.3, g=0.62, b=0.2)
# A fruit's colour as it ripens, at these ripenesses: green until it breaks,
# yellowing, orange, then red; between them, a blend of the two either side.
RIPENING_COLORS: Final = (
    (0.0, FRUIT_COLOR),
    (0.15, Color(r=0.72, g=0.74, b=0.28)),
    (0.45, Color(r=0.93, g=0.55, b=0.18)),
    (1.0, Color(r=0.8, g=0.1, b=0.07)),
)
# The sizes an organ's entity reports, by the organ's own field, rounded to
# this many decimals.
SIZES: Final = ("length_cm", "diameter_mm", "mass_g", "ripeness")
SIZE_DECIMALS: Final = 2


def fruit_color(ripeness: float) -> Color:
    """The colour of a fruit this ripe."""
    for (below, low), (above, high) in zip(RIPENING_COLORS, RIPENING_COLORS[1:], strict=False):
        if ripeness <= above:
            share = (ripeness - below) / (above - below)
            return Color(
                r=low.r * (1 - share) + high.r * share,
                g=low.g * (1 - share) + high.g * share,
                b=low.b * (1 - share) + high.b * share,
            )
    return RIPENING_COLORS[-1][1]


_KINDS: Final = {
    OrganKind.INTERNODE: (SceneEntityKind.INTERNODE, STEM_COLOR),
    OrganKind.LEAF: (SceneEntityKind.LEAF, LEAF_COLOR),
    OrganKind.TRUSS: (SceneEntityKind.TRUSS, TRUSS_COLOR),
    OrganKind.FLOWER: (SceneEntityKind.FLOWER, FLOWER_COLOR),
    OrganKind.FRUIT: (SceneEntityKind.FRUIT, FRUIT_COLOR),
}


def plant_entities(
    plant: Plant, at: Transform, context: Mapping[str, str] | None = None
) -> list[SceneEntity]:
    """Every shape of the plant as an entity, the plant standing at `at`, each
    also carrying `context`'s properties, such as the plant's environment."""
    organs = {organ_id: (kind, parent, organ) for kind, organ_id, parent, organ in plant.organs()}
    shared = {} if context is None else dict(context)
    return [_entity(plant, shape, at, organs, shared) for shape in organ_geometry(plant)]


def _entity(
    plant: Plant,
    shape: OrganShape,
    at: Transform,
    organs: dict[str, tuple[OrganKind, str | None, Organ]],
    context: dict[str, str],
) -> SceneEntity:
    kind, color = _KINDS[shape.kind]
    if shape.part in {"petiole", "rachis"}:
        color = RACHIS_COLOR
    _, parent, organ = organs[shape.organ_id]
    properties: dict[str, str | int | float | bool] = {
        "organ_id": shape.organ_id,
        "organ_kind": shape.kind.value,
        "part": shape.part,
        "plant_id": plant.plant_id,
        "parent_id": parent or "",
        "thermal_age_cd": round(plant.thermal_age(organ), 1),
        **context,
    }
    stage = getattr(organ, "stage", None)
    if stage is not None:
        properties["stage"] = str(stage)
    if stage == FlowerStage.BUD:
        color = BUD_COLOR
    for size in SIZES:
        value = getattr(organ, size, None)
        if isinstance(value, float):
            properties[size] = round(value, SIZE_DECIMALS)
    if isinstance(organ, Fruit):
        properties["maturity"] = maturity(organ.ripeness).value
        color = fruit_color(organ.ripeness)
    return SceneEntity(
        entity_id=shape.shape_id,
        kind=kind,
        transform=at.after(shape.transform),
        shape=shape.shape,
        color=color,
        label=shape.shape_id.replace("_", " "),
        properties=properties,
    )
