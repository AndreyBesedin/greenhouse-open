"""What stops an installation's draft running (P12.0, decision 0050).

A draft is an installation (`greenhouse_sim.scenarios.installation`) being
authored: a value no greenhouse can have is refused as the models refuse
it, and what only the parts together get wrong, such as a row reaching
through a wall, is a finding here instead, so that a draft can be kept and
edited until it can run.

A draft may give rows different crops, although a run grows one model and
one variety (`ScenarioConfig`); the assessment says so rather than refuse it.
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.domain.equipment import ActuatorKind
from greenhouse_sim.domain.layout import Obstruction
from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.world.envelope import Opening
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.layout import inside_the_greenhouse, outside_the_greenhouse
from greenhouse_sim.world.zones import EDGE_TOLERANCE_M

# How many of the items a finding concerns its message names; it counts the
# rest, and lists every one in its `items`.
NAMED_IN_A_MESSAGE: Final = 3


class Finding(BaseModel):
    """Something a draft gets wrong, or lacks: a stable code an editor
    reads, a message a person reads, and what it concerns, the layout's
    items by their ids and the crop rows by their numbers, so that an editor
    can point at them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Literal["error", "warning"]
    code: str
    message: str
    items: list[str] = []
    rows: list[int] = []


def named(things: list[str]) -> str:
    """The first of `things` by name, and how many more there are."""
    shown = ", ".join(things[:NAMED_IN_A_MESSAGE])
    more = len(things) - NAMED_IN_A_MESSAGE
    return shown if more <= 0 else f"{shown} and {more} more"


def assess_installation(draft: Installation) -> list[Finding]:
    """What stops a draft running, as errors, and what a greenhouse usually
    has that it lacks, as warnings: a research house may do without a
    door, vents, a heater or fans."""
    findings: list[Finding] = []
    outside = outside_the_greenhouse(draft.layout, draft.envelope)
    if outside:
        findings.append(
            Finding(
                severity="error",
                code="outside_envelope",
                message=f"Outside the greenhouse: {named(outside)}.",
                items=outside,
            )
        )
    inside = inside_the_greenhouse(draft.layout, draft.envelope)
    if inside:
        findings.append(
            Finding(
                severity="error",
                code="weather_station_inside",
                message=f"The weather station stands inside the greenhouse: {named(inside)}.",
                items=inside,
            )
        )
    findings += _collisions(draft)
    findings += _overlapping_openings(draft)
    findings += _crop_findings(draft)
    findings += _missing_equipment(draft)
    return findings


def _collisions(draft: Installation) -> list[Finding]:
    """A heater or a dehumidifier through another, or through a fixture in
    the way of movement or air, such as a row's supports: each pair named,
    as a finding of the pieces of equipment."""
    layout = draft.layout
    bodies = [
        piece.fixture()
        for piece in layout.equipment
        if Obstruction.MOVEMENT in piece.fixture().obstructs
    ]
    solid = [
        fixture
        for fixture in layout.fixtures()
        if {Obstruction.MOVEMENT, Obstruction.AIRFLOW} & fixture.obstructs
    ]
    pairs = [
        (body.fixture_id, other.fixture_id)
        for index, body in enumerate(bodies)
        for other in bodies[index + 1 :] + solid
        if _boxes_overlap(body.corners(), other.corners())
    ]
    if not pairs:
        return []
    clashing = [f"{one} with {other}" for one, other in pairs]
    return [
        Finding(
            severity="error",
            code="items_collide",
            message=f"Equipment through another item: {named(clashing)}.",
            items=sorted({name for pair in pairs for name in pair}),
        )
    ]


def _overlapping_openings(draft: Installation) -> list[Finding]:
    """Doors and vents that overlap on the surface they are on."""
    openings = draft.envelope.openings
    pairs = [
        (one.opening_id, other.opening_id)
        for index, one in enumerate(openings)
        for other in openings[index + 1 :]
        if one.surface_id == other.surface_id and _rectangles_overlap(one, other)
    ]
    if not pairs:
        return []
    return [
        Finding(
            severity="error",
            code="openings_overlap",
            message=f"Doors or vents overlap: {named([f'{a} with {b}' for a, b in pairs])}.",
            items=sorted({name for pair in pairs for name in pair}),
        )
    ]


def _rectangles_overlap(one: Opening, other: Opening) -> bool:
    """Whether two openings on one surface share more than an edge."""
    apart_x = abs(one.centre.x - other.centre.x) - (one.width + other.width) / 2
    apart_y = abs(one.centre.y - other.centre.y) - (one.height + other.height) / 2
    return apart_x < -EDGE_TOLERANCE_M and apart_y < -EDGE_TOLERANCE_M


def _boxes_overlap(one: list[Vector3], other: list[Vector3]) -> bool:
    """Whether two boxes, each by its corners as `Fixture.corners` gives
    them, share more than a face: no axis separates them, among each box's
    edges and the products of an edge of each (the separating axis
    theorem). A cylinder is taken as the box around it."""
    edges = _box_edges(one) + _box_edges(other)
    axes = edges + [a.cross(b) for a in _box_edges(one) for b in _box_edges(other)]
    for axis in axes:
        if axis.length() < _PARALLEL:
            continue
        on_one = [corner.dot(axis) / axis.length() for corner in one]
        on_other = [corner.dot(axis) / axis.length() for corner in other]
        if min(on_one) >= max(on_other) - EDGE_TOLERANCE_M:
            return False
        if min(on_other) >= max(on_one) - EDGE_TOLERANCE_M:
            return False
    return True


# A product of two edges this short comes of parallel edges, and separates
# nothing their own axes do not.
_PARALLEL: Final = 1e-9


def _box_edges(corners: list[Vector3]) -> list[Vector3]:
    """A box's three edges from its first corner: along its x, y and z, in
    the order `Fixture.corners` lists the corners (x, then y, then z)."""
    first = corners[0]
    return [
        Vector3(x=c.x - first.x, y=c.y - first.y, z=c.z - first.z)
        for c in (corners[4], corners[2], corners[1])
    ]


def _crop_findings(draft: Installation) -> list[Finding]:
    rows = draft.layout.crop_rows
    if rows is None:
        return [
            Finding(
                severity="error",
                code="missing_rows",
                message="No crop rows: a crop needs at least one.",
            )
        ]
    findings: list[Finding] = []
    numbers = range(1, rows.rows + 1)
    chosen = {crop.row for crop in draft.row_crops}
    unchosen = [row for row in numbers if row not in chosen]
    if unchosen:
        findings.append(
            Finding(
                severity="error",
                code="unassigned_rows",
                message=f"No crop chosen for rows {named([str(row) for row in unchosen])}.",
                rows=unchosen,
            )
        )
    planted = {position.row for position in draft.layout.planting_positions()}
    empty = [row for row in numbers if row not in planted]
    if empty:
        findings.append(
            Finding(
                severity="error",
                code="empty_rows",
                message=f"No planting position left in rows {named([str(row) for row in empty])}.",
                rows=empty,
            )
        )
    if len({(crop.crop_model, crop.variety) for crop in draft.row_crops}) > 1:
        findings.append(
            Finding(
                severity="error",
                code="mixed_crops_not_runnable",
                message="Rows grow different crops; a run grows one model and one variety.",
                rows=sorted(chosen),
            )
        )
    return findings


def _missing_equipment(draft: Installation) -> list[Finding]:
    openings = draft.envelope.openings
    equipment = {piece.kind for piece in draft.layout.equipment}
    missing = [
        ("no_door", "No door.", any(o.kind == OpeningKind.DOOR for o in openings)),
        ("no_vents", "No vent.", any(o.kind != OpeningKind.DOOR for o in openings)),
        ("no_heating", "No heater.", ActuatorKind.HEATER in equipment),
        ("no_fans", "No circulation fan.", ActuatorKind.FAN in equipment),
    ]
    return [
        Finding(severity="warning", code=code, message=message)
        for code, message, present in missing
        if not present
    ]
