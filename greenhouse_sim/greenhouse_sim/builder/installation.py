"""An installation draft, and what stops it running (P12.0, decision 0050).

A draft is made of the simulator's own models: an `Envelope`, a `Layout`,
and for each crop row the `CropModel` and variety it grows, the parts of a
scenario's manifest that describe the house. A value no greenhouse can have
is refused as the models refuse it. What only the parts together get wrong,
such as a row reaching through a wall, is a finding instead, so that a
draft can be kept and edited until it can run.

A draft may give rows different crops, although a run grows one model and
one variety (`ScenarioConfig`); the assessment says so rather than refuse it.
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationInfo, field_validator

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.domain.equipment import ActuatorKind
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.layout import Layout, inside_the_greenhouse, outside_the_greenhouse

# How many of the items a finding concerns its message names; it counts the
# rest, and lists every one in its `items`.
NAMED_IN_A_MESSAGE: Final = 3


class RowCrop(BaseModel):
    """The crop one row grows: its model and its variety. Rows are numbered
    from 1, as `CropRows` numbers them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    row: PositiveInt
    crop_model: CropModel
    variety: str = Field(min_length=1)


class InstallationDraft(BaseModel):
    """A greenhouse as authored: no weather, period, control or policy,
    which are a scenario's."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    installation_id: ItemId
    name: str = Field(min_length=1)
    envelope: Envelope
    layout: Layout
    row_crops: list[RowCrop] = []

    # Checked as the field, so that a refusal points at it; the layout,
    # before it, is read already, unless it was refused itself.
    @field_validator("row_crops")
    @classmethod
    def _each_row_has_one_crop_at_most(
        cls, crops: list[RowCrop], info: ValidationInfo
    ) -> list[RowCrop]:
        first: dict[int, int] = {}
        for index, crop in enumerate(crops):
            if crop.row in first:
                raise ValueError(
                    f"row {crop.row} has more than one crop, at [{first[crop.row]}] and [{index}]"
                )
            first[crop.row] = index
        layout = info.data.get("layout")
        if isinstance(layout, Layout):
            total = 0 if layout.crop_rows is None else layout.crop_rows.rows
            beyond = sorted(crop.row for crop in crops if crop.row > total)
            if beyond:
                raise ValueError(f"crops for rows {beyond}, beyond the layout's {total} rows")
        return crops


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


def assess_installation(draft: InstallationDraft) -> list[Finding]:
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
    findings += _crop_findings(draft)
    findings += _missing_equipment(draft)
    return findings


def _crop_findings(draft: InstallationDraft) -> list[Finding]:
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


def _missing_equipment(draft: InstallationDraft) -> list[Finding]:
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
