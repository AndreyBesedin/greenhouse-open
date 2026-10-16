from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from greenhouse_protocol.enums import SourceType
from greenhouse_protocol.instant import Instant


class Plant(BaseModel):
    model_config = ConfigDict(frozen=True)

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

    model_config = ConfigDict(frozen=True)

    kind: Literal["grid", "compartment"] = "grid"
    rows: int = Field(ge=0)
    columns: int = Field(ge=0)


class Compartment(BaseModel):
    """A physically separate growing space inside a greenhouse, with its own
    climate and control: a WUR trial compartment, a research cell, a
    section behind its own screens. Readings, events and state can be
    scoped to a compartment; a greenhouse with no compartments (the
    simulator today) scopes everything to the greenhouse itself."""

    model_config = ConfigDict(frozen=True)

    compartment_id: str  # unique within its greenhouse, e.g. "3.06"
    name: str
    description: str = ""
    # Individually identified plants in this compartment, when the source
    # knows them; empty when it only observes the compartment as a whole.
    plants: tuple[Plant, ...] = ()


class GreenhouseDescription(BaseModel):
    """What a producer states about a greenhouse: identity, crop, layout,
    compartments and known plants.

    Any producer can emit it and any consumer can read it. What a consumer
    adds on top - who owns the greenhouse, how far a replay has got - is the
    consumer's own record, typically a subclass of this one.

    It is edited by assigning a field, and each edit is checked as the
    description was when built: one that is refused leaves it as it was.
    Its layout, compartments and plants are values, so an edit replaces one.
    """

    model_config = ConfigDict(validate_assignment=True)

    greenhouse_id: str
    name: str
    description: str
    source_type: SourceType
    # The crop grown, independent of whether individual plants are known.
    crop: str | None = None
    layout: GreenhouseLayout
    # Plants not assigned to any compartment (the simulator's grid).
    plants: tuple[Plant, ...]
    compartments: tuple[Compartment, ...] = ()
    created_at: Instant

    # Identities are checked field by field, each against the other field's
    # current value, rather than on the whole model: pydantic stores an
    # assignment before a model validator runs, so a refused edit would stay.
    @field_validator("plants")
    @classmethod
    def _plant_ids_are_unique(
        cls, plants: tuple[Plant, ...], info: ValidationInfo
    ) -> tuple[Plant, ...]:
        _refuse_duplicates("plant", _plant_ids(plants, info.data.get("compartments", ())))
        return plants

    @field_validator("compartments")
    @classmethod
    def _compartment_and_plant_ids_are_unique(
        cls, compartments: tuple[Compartment, ...], info: ValidationInfo
    ) -> tuple[Compartment, ...]:
        _refuse_duplicates("compartment", [c.compartment_id for c in compartments])
        _refuse_duplicates("plant", _plant_ids(info.data.get("plants", ()), compartments))
        return compartments

    @property
    def all_plants(self) -> tuple[Plant, ...]:
        """Every plant in the greenhouse, unassigned ones first, then
        compartment by compartment in declaration order."""
        return (*self.plants, *(p for c in self.compartments for p in c.plants))

    def compartment(self, compartment_id: str) -> Compartment | None:
        return next((c for c in self.compartments if c.compartment_id == compartment_id), None)


def _plant_ids(plants: tuple[Plant, ...], compartments: tuple[Compartment, ...]) -> list[str]:
    return [p.plant_id for p in (*plants, *(p for c in compartments for p in c.plants))]


def _refuse_duplicates(kind: str, ids: list[str]) -> None:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in ids:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    if repeated:
        raise ValueError(f"duplicate {kind} ids: {sorted(repeated)}")


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
