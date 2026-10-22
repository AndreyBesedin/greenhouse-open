"""Portable greenhouse installation drafts, independent of a simulation run.

An installation uses the simulator's own Envelope and Layout models. The
row-to-crop references are authoring metadata: until the simulator can
resolve model revisions and grow heterogeneous rows, they are not executable
simulation configuration.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.layout import Layout, inside_the_greenhouse, outside_the_greenhouse


class RowCrop(BaseModel):
    """The model and variety chosen for one row, numbered from one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    row: PositiveInt
    model_id: ItemId
    # An immutable model revision will be required for publication; a draft
    # can follow a working version while it is being edited.
    model_revision: ItemId | None = None
    variety: str = Field(min_length=1)


class InstallationDraft(BaseModel):
    """A portable edit snapshot; no weather, control, time or policy is here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    installation_id: ItemId
    name: str = Field(min_length=1)
    envelope: Envelope
    layout: Layout
    row_crops: list[RowCrop] = []

    @model_validator(mode="after")
    def _row_assignments_are_unique_and_refer_to_rows(self) -> Self:
        indexes = [assignment.row for assignment in self.row_crops]
        if len(indexes) != len(set(indexes)):
            raise ValueError("a crop row has more than one crop assignment")
        total = 0 if self.layout.crop_rows is None else self.layout.crop_rows.rows
        if any(index > total for index in indexes):
            raise ValueError(f"a crop assignment names a row beyond the {total} rows")
        return self


class Finding(BaseModel):
    """A stable code for the UI, with a human-readable explanation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Literal["error", "warning"]
    code: str
    message: str


def assess_installation(draft: InstallationDraft) -> list[Finding]:
    """Issues that need fixing, and optional facilities that deserve a warning.

    Base model validation rejects impossible dimensions, invalid openings,
    repeated equipment identifiers and overlapping supports before this
    function runs. Cross-object geometry and simulation readiness are
    assessed here so an incomplete draft can still be edited.
    """
    findings: list[Finding] = []

    def report(severity: Literal["error", "warning"], code: str, message: str) -> None:
        findings.append(Finding(severity=severity, code=code, message=message))

    outside = outside_the_greenhouse(draft.layout, draft.envelope)
    if outside:
        report("error", "outside_envelope", f"Items outside the greenhouse: {', '.join(outside[:3])}")
    inside = inside_the_greenhouse(draft.layout, draft.envelope)
    if inside:
        report("error", "weather_station_inside", f"Weather station must be outside: {inside[0]}")

    rows = draft.layout.crop_rows
    if rows is None:
        report("error", "missing_rows", "Add a crop row before running a crop simulation.")
    else:
        assigned = {row.row for row in draft.row_crops}
        missing = [row for row in range(1, rows.rows + 1) if row not in assigned]
        if missing:
            report("error", "unassigned_rows", f"Choose a crop for rows: {', '.join(map(str, missing))}")
        planted = {position.row for position in draft.layout.planting_positions()}
        empty = [row for row in range(1, rows.rows + 1) if row not in planted]
        if empty:
            report("error", "empty_rows", f"No planting positions remain in rows: {', '.join(map(str, empty))}")
        # Today ScenarioConfig has one variety and one CropModel for all rows.
        kinds = {(row.model_id, row.model_revision, row.variety) for row in draft.row_crops}
        if len(kinds) > 1:
            report(
                "error",
                "mixed_crops_not_runnable",
                "Different row crops can be drafted, but current simulations grow one model and variety.",
            )

    if not any(opening.kind == OpeningKind.DOOR for opening in draft.envelope.openings):
        report("warning", "no_door", "No door has been placed.")
    if not any(opening.kind != OpeningKind.DOOR for opening in draft.envelope.openings):
        report("warning", "no_vents", "No ventilation opening has been placed.")
    if not any(piece.kind == "heater" for piece in draft.layout.equipment):
        report("warning", "no_heating", "No heater has been placed; this may be intentional.")
    if not any(piece.kind == "fan" for piece in draft.layout.equipment):
        report("warning", "no_fans", "No circulation fan has been placed.")

    return findings
