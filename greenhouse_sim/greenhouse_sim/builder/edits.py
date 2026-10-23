"""An edit of many items as a client sends it (P12.3): which of
`builder.items`'s edits it is, by its `edit`, and what that edit is given,
as data. The simulator checks and applies it, so that a builder makes no
edit of its own.

Their JSON Schema is published as `edit.schema.json`, for a client to write
them from.
"""

from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from greenhouse_sim.builder.items import (
    MOST_AT_ONCE,
    Axis,
    place_items,
    place_openings,
    remove_items,
    repeat_items,
    repeat_openings,
    set_field,
    space_items,
    space_openings,
    spread_openings,
)
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT
from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.world.envelope import Opening
from greenhouse_sim.world.equipment import Equipment
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.sensors import Sensor

# How many items one edit places or copies of each: as many as
# `MOST_AT_ONCE` allows in all.
type Count = Annotated[int, Field(ge=1, le=MOST_AT_ONCE)]


class _Edit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PlaceItems(_Edit):
    """Pieces of equipment or sensors like `item`, the first where it
    stands and each next `step` further, named after its identifier."""

    edit: Literal["place_items"] = "place_items"
    item: Equipment | Sensor
    count: Count = 1
    step: Vector3 | None = None

    def apply(self, draft: Installation) -> Installation:
        return place_items(draft, self.item, count=self.count, step=self.step)


class RepeatItems(_Edit):
    """Each chosen piece of equipment or sensor copied `count` times, each
    copy `step` further than the one before."""

    edit: Literal["repeat_items"] = "repeat_items"
    items: list[str]
    count: Count
    step: Vector3

    def apply(self, draft: Installation) -> Installation:
        return repeat_items(draft, self.items, count=self.count, step=self.step)


class SpaceItems(_Edit):
    """The chosen pieces of equipment and sensors spaced evenly along an
    axis of the greenhouse."""

    edit: Literal["space_items"] = "space_items"
    items: list[str]
    axis: Axis

    def apply(self, draft: Installation) -> Installation:
        return space_items(draft, self.items, axis=self.axis)


class PlaceOpenings(_Edit):
    """On each chosen surface, doors or vents like `opening`, the first at
    its centre and each next `step` further in the surface's plane."""

    edit: Literal["place_openings"] = "place_openings"
    opening: Opening
    surfaces: list[str]
    count: Count = 1
    step: Point2 | None = None

    def apply(self, draft: Installation) -> Installation:
        return place_openings(draft, self.opening, self.surfaces, count=self.count, step=self.step)


class SpreadOpenings(_Edit):
    """On each chosen surface, `count` doors or vents like `opening`, spread
    evenly along it."""

    edit: Literal["spread_openings"] = "spread_openings"
    opening: Opening
    surfaces: list[str]
    count: Count

    def apply(self, draft: Installation) -> Installation:
        return spread_openings(draft, self.opening, self.surfaces, count=self.count)


class RepeatOpenings(_Edit):
    """Each chosen door or vent copied `count` times on its surface, each
    copy `step` further than the one before."""

    edit: Literal["repeat_openings"] = "repeat_openings"
    openings: list[str]
    count: Count
    step: Point2

    def apply(self, draft: Installation) -> Installation:
        return repeat_openings(draft, self.openings, count=self.count, step=self.step)


class SpaceOpenings(_Edit):
    """The chosen doors and vents of one surface spaced evenly along it."""

    edit: Literal["space_openings"] = "space_openings"
    openings: list[str]

    def apply(self, draft: Installation) -> Installation:
        return space_openings(draft, self.openings)


class SetField(_Edit):
    """One field, a nested one by its path (`base.z`), given one value over
    the chosen items: equipment, sensors, doors or vents."""

    edit: Literal["set_field"] = "set_field"
    items: list[str]
    path: str = Field(min_length=1)
    value: JsonValue

    def apply(self, draft: Installation) -> Installation:
        return set_field(draft, self.items, self.path, self.value)


class RemoveItems(_Edit):
    """The chosen equipment, sensors, doors and vents taken out."""

    edit: Literal["remove_items"] = "remove_items"
    items: list[str]

    def apply(self, draft: Installation) -> Installation:
        return remove_items(draft, self.items)


type Edit = Annotated[
    PlaceItems
    | RepeatItems
    | SpaceItems
    | PlaceOpenings
    | SpreadOpenings
    | RepeatOpenings
    | SpaceOpenings
    | SetField
    | RemoveItems,
    Field(discriminator="edit"),
]

EDITS: Final = TypeAdapter[Edit](Edit)


def edit_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema of an edit, published as `edit.schema.json`: what a
    client sends, so that a field with a default may be left out."""
    schema = EDITS.json_schema()
    return {"$schema": JSON_SCHEMA_DIALECT, "title": "Edit", **schema}
