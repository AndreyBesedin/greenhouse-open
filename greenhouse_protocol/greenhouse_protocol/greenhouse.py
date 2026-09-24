from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from greenhouse_protocol.enums import SourceType


class Plant(BaseModel):
    plant_id: str
    variety: str
    row: int
    position_in_row: int
    x: float | None = None
    y: float | None = None
    zone: str | None = None
    tray_id: str | None = None


class GreenhouseLayout(BaseModel):
    """ "grid": plants laid out in rows x columns (the simulator). "compartment":
    a physical compartment observed as a whole, with no individually
    identified plants (a recorded dataset's climate compartment) - rows and
    columns are then 0. Positions inside a compartment are a later spatial
    model."""

    kind: Literal["grid", "compartment"] = "grid"
    rows: int = Field(ge=0)
    columns: int = Field(ge=0)


class Compartment(BaseModel):
    """A physically separate growing space inside a greenhouse, with its own
    climate and control: a WUR trial compartment, a research cell, a
    section behind its own screens. Readings, events and state can be
    scoped to a compartment; a greenhouse with no compartments (the
    simulator today) scopes everything to the greenhouse itself."""

    compartment_id: str  # unique within its greenhouse, e.g. "3.06"
    name: str
    description: str = ""
    # Individually identified plants in this compartment, when the source
    # knows them; empty when it only observes the compartment as a whole.
    plants: list[Plant] = Field(default_factory=list)


class GreenhouseDescription(BaseModel):
    """What a producer states about a greenhouse: identity, crop, layout,
    compartments and known plants.

    Any producer can emit it and any consumer can read it. What a consumer
    adds on top - who owns the greenhouse, how far a replay has got - is the
    consumer's own record, typically a subclass of this one.
    """

    greenhouse_id: str
    name: str
    description: str
    source_type: SourceType
    # The crop grown, independent of whether individual plants are known.
    crop: str | None = None
    layout: GreenhouseLayout
    # Plants not assigned to any compartment (the simulator's grid).
    plants: list[Plant]
    compartments: list[Compartment] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def _identities_are_unique(self) -> "GreenhouseDescription":
        compartment_ids = [c.compartment_id for c in self.compartments]
        duplicates = _duplicates(compartment_ids)
        if duplicates:
            raise ValueError(f"duplicate compartment ids: {sorted(duplicates)}")
        plant_ids = [p.plant_id for p in self.all_plants]
        duplicates = _duplicates(plant_ids)
        if duplicates:
            raise ValueError(f"duplicate plant ids: {sorted(duplicates)}")
        return self

    @property
    def all_plants(self) -> list[Plant]:
        """Every plant in the greenhouse, unassigned ones first, then
        compartment by compartment in declaration order."""
        return [*self.plants, *(p for c in self.compartments for p in c.plants)]

    def compartment(self, compartment_id: str) -> Compartment | None:
        return next((c for c in self.compartments if c.compartment_id == compartment_id), None)


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return repeated


def build_grid_plants(greenhouse_id: str, variety: str, rows: int, columns: int) -> list[Plant]:
    plants = []
    index = 0
    for row in range(1, rows + 1):
        for position_in_row in range(1, columns + 1):
            index += 1
            plants.append(
                Plant(
                    plant_id=f"{greenhouse_id}_plant_{index:03d}",
                    variety=variety,
                    row=row,
                    position_in_row=position_in_row,
                )
            )
    return plants
