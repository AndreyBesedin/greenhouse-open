"""Equipment, sensors, doors and vents placed, copied, spaced, changed and
removed many at a time (P12.3).

Each edit checks all it is asked to change, and the installation it makes,
before changing anything, and returns a new installation, so that an editor
keeps the one before for its undo, as the rows' edits do
(`greenhouse_sim.builder.batch`). The installation made is checked as a file
of it is read: what the models refuse, such as a heater on a walkway or a
vent off its roof, refuses the edit, with their reason; what only the parts
together get wrong is a finding of its assessment instead
(`greenhouse_sim.builder.installation`).

A new item is named after the item it copies, or the stem it is given, and
the lowest number no item of the installation has: copies of `fan_2` are
`fan_1` if it is free, then `fan_3`. The same edit of the same draft always
names its items the same.

Positions are in metres, in the greenhouse's frame: a piece of equipment's
or a sensor's in the house (`greenhouse_sim.world.moves.displaced`), an
opening's in the plane of the surface it is on, as its `centre` is.
"""

import re
from collections.abc import Iterable, Sequence
from typing import Final, Literal, TypeIs

from pydantic import JsonValue, TypeAdapter

from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.world.envelope import Envelope, Opening, outline
from greenhouse_sim.world.equipment import Dehumidifier, Equipment, Fan, Heater
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.moves import displaced
from greenhouse_sim.world.sensors import Sensor

# The most items one edit adds: more than a greenhouse's vents or fans.
MOST_AT_ONCE: Final = 500
# How few items spacing takes: two stay where they are, and the rest are
# spaced between them.
FEWEST_TO_SPACE: Final = 3
# What a new item's name ends in, after its stem.
_NUMBERED: Final = re.compile(r"_\d+$")
# Which of an item's fields its identifier is.
_ID_FIELDS: Final = ("actuator_id", "sensor_id", "opening_id")

type Item = Equipment | Sensor
type Axis = Literal["x", "y", "z"]

_EQUIPMENT: Final = TypeAdapter[Equipment](Equipment)
_SENSOR: Final = TypeAdapter[Sensor](Sensor)


def names_taken(draft: Installation) -> set[str]:
    """Every identifier the installation gives an item: its fixtures,
    zones, equipment, sensors, doors and vents."""
    layout = draft.layout
    return (
        {fixture.fixture_id for fixture in layout.fixtures()}
        | {zone.zone_id for zone in layout.zones}
        | {piece.actuator_id for piece in layout.equipment}
        | {sensor.sensor_id for sensor in layout.sensors}
        | {opening.opening_id for opening in draft.envelope.openings}
    )


def place_items(
    draft: Installation, item: Item, *, count: int = 1, step: Vector3 | None = None
) -> Installation:
    """`count` pieces of equipment or sensors like `item`, the first where
    it stands and each next `step` further, named after its identifier.
    Refused if the count is not from 1 to `MOST_AT_ONCE`, or if more than
    one would stand in one place."""
    _check_count(count, step is not None and step != _NOWHERE)
    names = _numbered([_id(item)] * count, names_taken(draft))
    by = step or _NOWHERE
    added = [_renamed(displaced(item, _times(by, k)), name) for k, name in enumerate(names)]
    return _with_items(draft, added=added)


def repeat_items(
    draft: Installation, item_ids: Sequence[str], *, count: int, step: Vector3
) -> Installation:
    """Each chosen piece of equipment or sensor copied `count` times, each
    copy `step` further than the one before, named after it. Refused if no
    item is chosen, one is not the layout's, or the step is none."""
    chosen = _chosen_items(draft, item_ids)
    _check_count(count * len(chosen), step != _NOWHERE)
    names = iter(
        _numbered([_id(item) for item in chosen for _ in range(count)], names_taken(draft))
    )
    added = [
        _renamed(displaced(item, _times(step, k)), next(names))
        for item in chosen
        for k in range(1, count + 1)
    ]
    return _with_items(draft, added=added)


def space_items(draft: Installation, item_ids: Sequence[str], *, axis: Axis) -> Installation:
    """The chosen pieces of equipment and sensors spaced evenly along an
    axis of the greenhouse, between the two that stand furthest apart along
    it, which stay; each keeps its other coordinates. Refused if fewer than
    three are chosen."""
    chosen = _chosen_items(draft, item_ids)
    if len(chosen) < FEWEST_TO_SPACE:
        raise ValueError("choose at least three items to space")
    ordered = sorted(chosen, key=lambda item: _along(_place(item), axis))
    first, last = _along(_place(ordered[0]), axis), _along(_place(ordered[-1]), axis)
    gap = (last - first) / (len(ordered) - 1)
    moved = {
        _id(item): displaced(item, _on(axis, first + gap * k - _along(_place(item), axis)))
        for k, item in enumerate(ordered)
    }
    return _with_items(draft, replaced=moved)


def place_openings(
    draft: Installation,
    opening: Opening,
    surface_ids: Sequence[str],
    *,
    count: int = 1,
    step: Point2 | None = None,
) -> Installation:
    """On each chosen surface, `count` doors or vents like `opening`, the
    first at its centre and each next `step` further in the surface's
    plane, named after its identifier. Refused if no surface is chosen, one
    is not the envelope's, or more than one would stand in one place."""
    surfaces = _chosen_surfaces(draft.envelope, surface_ids)
    # One on each surface needs no step: only several on one surface do.
    _check_count(count * len(surfaces), count == 1 or (step is not None and step != _ON_THE_SPOT))
    names = iter(_numbered([opening.opening_id] * (count * len(surfaces)), names_taken(draft)))
    by = step or _ON_THE_SPOT
    added = [
        _placed_opening(opening, next(names), surface, _shifted(opening.centre, by, k))
        for surface in surfaces
        for k in range(count)
    ]
    return _with_openings(draft, added=added)


def spread_openings(
    draft: Installation, opening: Opening, surface_ids: Sequence[str], *, count: int
) -> Installation:
    """On each chosen surface, `count` doors or vents like `opening`, spread
    evenly along the surface's length, each centred on its share of it, at
    the height in the surface `opening` is centred at: a row of vents along
    each roof slope chosen."""
    surfaces = _chosen_surfaces(draft.envelope, surface_ids)
    _check_count(count * len(surfaces), True)
    hosts = {surface.surface_id: surface for surface in draft.envelope.surfaces()}
    names = iter(_numbered([opening.opening_id] * (count * len(surfaces)), names_taken(draft)))
    added = []
    for surface in surfaces:
        xs = [corner.x for corner in outline(hosts[surface].shape)]
        start, share = min(xs), (max(xs) - min(xs)) / count
        added += [
            _placed_opening(
                opening,
                next(names),
                surface,
                Point2(x=start + share * (k + 0.5), y=opening.centre.y),
            )
            for k in range(count)
        ]
    return _with_openings(draft, added=added)


def repeat_openings(
    draft: Installation, opening_ids: Sequence[str], *, count: int, step: Point2
) -> Installation:
    """Each chosen door or vent copied `count` times on its surface, each
    copy `step` further in the surface's plane than the one before."""
    chosen = _chosen_openings(draft, opening_ids)
    _check_count(count * len(chosen), step != _ON_THE_SPOT)
    names = iter(
        _numbered([o.opening_id for o in chosen for _ in range(count)], names_taken(draft))
    )
    added = [
        _placed_opening(o, next(names), o.surface_id, _shifted(o.centre, step, k))
        for o in chosen
        for k in range(1, count + 1)
    ]
    return _with_openings(draft, added=added)


def space_openings(draft: Installation, opening_ids: Sequence[str]) -> Installation:
    """The chosen doors and vents of one surface spaced evenly along it,
    between the two furthest apart, which stay. Refused if fewer than three
    are chosen, or they are on more than one surface."""
    chosen = _chosen_openings(draft, opening_ids)
    if len(chosen) < FEWEST_TO_SPACE:
        raise ValueError("choose at least three doors or vents to space")
    if len({o.surface_id for o in chosen}) > 1:
        raise ValueError("choose doors or vents of one surface to space")
    ordered = sorted(chosen, key=lambda o: o.centre.x)
    first, last = ordered[0].centre.x, ordered[-1].centre.x
    gap = (last - first) / (len(ordered) - 1)
    moved = {
        o.opening_id: o.model_copy(update={"centre": Point2(x=first + gap * k, y=o.centre.y)})
        for k, o in enumerate(ordered)
    }
    return _with_openings(draft, replaced=moved)


def set_field(
    draft: Installation, item_ids: Sequence[str], path: str, value: JsonValue
) -> Installation:
    """One field given one value over the chosen items, equipment, sensors,
    doors or vents alike: `power_w`, or a nested one by its path, as
    `base.z`. Refused if an item chosen has no such field, if the value is
    not one the field takes, or if it names more than one item."""
    keys = path.split(".")
    if keys[0] in _ID_FIELDS and len(set(item_ids)) > 1:
        raise ValueError("rename one item at a time")
    openings = {o.opening_id: o for o in draft.envelope.openings}
    items = {_id(item): item for item in _items(draft)}
    unknown = [name for name in item_ids if name not in openings and name not in items]
    if not item_ids:
        raise ValueError("choose at least one item")
    if unknown:
        raise ValueError(f"no item {', '.join(unknown)}")
    changed_items: dict[str, Item] = {}
    changed_openings: dict[str, Opening] = {}
    for name in dict.fromkeys(item_ids):
        if name in openings:
            given = _with_value(openings[name].model_dump(), keys, value, name, path)
            changed_openings[name] = Opening.model_validate(given)
            continue
        item = items[name]
        given = _with_value(item.model_dump(), keys, value, name, path)
        adapter = _EQUIPMENT if _is_equipment(item) else _SENSOR
        changed_items[name] = adapter.validate_python(given)
    draft = _with_openings(draft, replaced=changed_openings)
    return _with_items(draft, replaced=changed_items)


def remove_items(draft: Installation, item_ids: Sequence[str]) -> Installation:
    """The chosen equipment, sensors, doors and vents taken out of the
    draft. Refused if none is chosen, or one is not the draft's."""
    chosen = set(item_ids)
    present = {_id(item) for item in _items(draft)} | {
        o.opening_id for o in draft.envelope.openings
    }
    if not chosen:
        raise ValueError("choose at least one item")
    unknown = sorted(chosen - present)
    if unknown:
        raise ValueError(f"no item {', '.join(unknown)}")
    layout = draft.layout
    return _remade(
        draft,
        equipment=[p for p in layout.equipment if p.actuator_id not in chosen],
        sensors=[s for s in layout.sensors if s.sensor_id not in chosen],
        openings=[o for o in draft.envelope.openings if o.opening_id not in chosen],
    )


_NOWHERE: Final = Vector3(x=0.0, y=0.0, z=0.0)
_ON_THE_SPOT: Final = Point2(x=0.0, y=0.0)


def _check_count(count: int, apart: bool) -> None:
    if not 1 <= count <= MOST_AT_ONCE:
        raise ValueError(f"place from 1 to {MOST_AT_ONCE} items at once")
    if count > 1 and not apart:
        raise ValueError("give a step, or the items would stand in one place")


def _numbered(asked: Iterable[str], taken: set[str]) -> list[str]:
    """A new name for each identifier asked: its stem, without a number it
    ends in, and the lowest number no item has, in the order asked."""
    names: list[str] = []
    used = set(taken)
    for given in asked:
        stem = _NUMBERED.sub("", given)
        number = 1
        while f"{stem}_{number}" in used:
            number += 1
        used.add(f"{stem}_{number}")
        names.append(f"{stem}_{number}")
    return names


def _id(item: Item | Opening) -> str:
    if isinstance(item, Opening):
        return item.opening_id
    return item.actuator_id if _is_equipment(item) else item.sensor_id


def _is_equipment(item: Item) -> TypeIs[Fan | Heater | Dehumidifier]:
    return isinstance(item, Fan | Heater | Dehumidifier)


def _renamed[Named: (Item, Opening)](item: Named, name: str) -> Named:
    field = next(field for field in _ID_FIELDS if hasattr(item, field))
    return item.model_copy(update={field: name})


def _items(draft: Installation) -> list[Item]:
    return [*draft.layout.equipment, *draft.layout.sensors]


def _chosen_items(draft: Installation, item_ids: Sequence[str]) -> list[Item]:
    if not item_ids:
        raise ValueError("choose at least one item")
    items = {_id(item): item for item in _items(draft)}
    unknown = [name for name in item_ids if name not in items]
    if unknown:
        raise ValueError(f"no equipment or sensor {', '.join(unknown)}")
    return [items[name] for name in dict.fromkeys(item_ids)]


def _chosen_openings(draft: Installation, opening_ids: Sequence[str]) -> list[Opening]:
    if not opening_ids:
        raise ValueError("choose at least one door or vent")
    openings = {o.opening_id: o for o in draft.envelope.openings}
    unknown = [name for name in opening_ids if name not in openings]
    if unknown:
        raise ValueError(f"no door or vent {', '.join(unknown)}")
    return [openings[name] for name in dict.fromkeys(opening_ids)]


def _chosen_surfaces(envelope: Envelope, surface_ids: Sequence[str]) -> list[str]:
    if not surface_ids:
        raise ValueError("choose at least one surface")
    known = {surface.surface_id for surface in envelope.surfaces()}
    unknown = [name for name in surface_ids if name not in known]
    if unknown:
        raise ValueError(f"no surface {', '.join(unknown)}")
    return list(dict.fromkeys(surface_ids))


def _place(item: Item) -> Vector3:
    return item.base if isinstance(item, Heater | Dehumidifier) else item.position


def _along(point: Vector3, axis: Axis) -> float:
    return {"x": point.x, "y": point.y, "z": point.z}[axis]


def _on(axis: Axis, distance: float) -> Vector3:
    return Vector3(
        x=distance if axis == "x" else 0.0,
        y=distance if axis == "y" else 0.0,
        z=distance if axis == "z" else 0.0,
    )


def _times(step: Vector3, k: int) -> Vector3:
    return Vector3(x=step.x * k, y=step.y * k, z=step.z * k)


def _shifted(centre: Point2, step: Point2, k: int) -> Point2:
    return Point2(x=centre.x + step.x * k, y=centre.y + step.y * k)


def _placed_opening(opening: Opening, name: str, surface_id: str, centre: Point2) -> Opening:
    return opening.model_copy(
        update={"opening_id": name, "surface_id": surface_id, "centre": centre}
    )


def _with_value(
    fields: dict[str, object], keys: list[str], value: JsonValue, name: str, path: str
) -> dict[str, object]:
    """The item's fields with the one at `keys` given `value`, refused if it
    has none there."""
    *parents, last = keys
    holder: object = fields
    for key in parents:
        holder = holder.get(key) if isinstance(holder, dict) else None
    if not isinstance(holder, dict) or last not in holder:
        raise ValueError(f"{name} has no {path}")
    holder[last] = value
    return fields


def _with_items(
    draft: Installation,
    *,
    added: Sequence[Item] = (),
    replaced: dict[str, Item] | None = None,
) -> Installation:
    swaps = replaced or {}

    def swap(item: Item) -> Item:
        return swaps.get(_id(item), item)

    layout = draft.layout
    equipment = [swap(p) for p in layout.equipment]
    sensors = [swap(s) for s in layout.sensors]
    for item in added:
        if _is_equipment(item):
            equipment.append(item)
        else:
            sensors.append(item)
    return _remade(draft, equipment=equipment, sensors=sensors)


def _with_openings(
    draft: Installation,
    *,
    added: Sequence[Opening] = (),
    replaced: dict[str, Opening] | None = None,
) -> Installation:
    kept = [(replaced or {}).get(o.opening_id, o) for o in draft.envelope.openings]
    return _remade(draft, openings=[*kept, *added])


def _remade(
    draft: Installation,
    *,
    equipment: Sequence[Item] | None = None,
    sensors: Sequence[Item] | None = None,
    openings: Sequence[Opening] | None = None,
) -> Installation:
    """The draft with its items replaced, checked as a file of it is read:
    the layout's, the envelope's and the installation's own checks."""
    layout = Layout.model_validate(
        dict(draft.layout)
        | ({} if equipment is None else {"equipment": list(equipment)})
        | ({} if sensors is None else {"sensors": list(sensors)})
    )
    envelope = Envelope.model_validate(
        dict(draft.envelope) | ({} if openings is None else {"openings": list(openings)})
    )
    return Installation.model_validate(dict(draft) | {"layout": layout, "envelope": envelope})
