"""Plants organ by organ, as a viewer draws them.

Each shape of a plant's geometry (`greenhouse_sim.biology.tomato.organ.geometry`)
becomes an entity of its organ's kind, placed where the plant stands. Its
properties say which organ it is and which part of it, where that organ sits
in the plant, and how far it has developed, so a viewer can inspect any organ
and rebuild the plant's structure from what it draws.
"""

from typing import Final

from greenhouse_sim.biology.tomato.organ.geometry import OrganShape, organ_geometry
from greenhouse_sim.biology.tomato.organ.topology import Organ, OrganKind, Plant
from greenhouse_sim.scene.snapshot import Color, SceneEntity, SceneEntityKind
from greenhouse_sim.world.geometry import Transform

STEM_COLOR: Final = Color(r=0.36, g=0.56, b=0.24)
LEAF_COLOR: Final = Color(r=0.18, g=0.5, b=0.2)
# A leaf's petiole and rachis are paler than its leaflets.
RACHIS_COLOR: Final = Color(r=0.4, g=0.62, b=0.26)
TRUSS_COLOR: Final = Color(r=0.42, g=0.6, b=0.28)
FLOWER_COLOR: Final = Color(r=0.96, g=0.84, b=0.18)
FRUIT_COLOR: Final = Color(r=0.3, g=0.62, b=0.2)

_KINDS: Final = {
    OrganKind.INTERNODE: (SceneEntityKind.INTERNODE, STEM_COLOR),
    OrganKind.LEAF: (SceneEntityKind.LEAF, LEAF_COLOR),
    OrganKind.TRUSS: (SceneEntityKind.TRUSS, TRUSS_COLOR),
    OrganKind.FLOWER: (SceneEntityKind.FLOWER, FLOWER_COLOR),
    OrganKind.FRUIT: (SceneEntityKind.FRUIT, FRUIT_COLOR),
}


def plant_entities(plant: Plant, at: Transform) -> list[SceneEntity]:
    """Every shape of the plant as an entity, the plant standing at `at`."""
    organs = {organ_id: (kind, parent, organ) for kind, organ_id, parent, organ in plant.organs()}
    return [_entity(plant, shape, at, organs) for shape in organ_geometry(plant)]


def _entity(
    plant: Plant,
    shape: OrganShape,
    at: Transform,
    organs: dict[str, tuple[OrganKind, str | None, Organ]],
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
    }
    stage = getattr(organ, "stage", None)
    if stage is not None:
        properties["stage"] = str(stage)
    return SceneEntity(
        entity_id=shape.shape_id,
        kind=kind,
        transform=at.after(shape.transform),
        shape=shape.shape,
        color=color,
        label=shape.shape_id.replace("_", " "),
        properties=properties,
    )
