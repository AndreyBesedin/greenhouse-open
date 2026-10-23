"""A first draft from a few values a person fills in before any preview:
a pitched house of equal spans and bays, and parallel rows of one crop
(P12.0)."""

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PositiveFloat, PositiveInt

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT
from greenhouse_sim.scenarios.installation import Installation, RowCrop
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Point2
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import TOMATO_GUTTER, CropRows, RowSupport

# A house the first form starts from: a small single-span one of two rows,
# as the climate box is (published as the form's schema's example).
STARTING_HOUSE: Final[dict[str, JsonValue]] = {
    "installation_id": "my_greenhouse",
    "name": "My greenhouse",
    "length_m": 12.0,
    "width_m": 6.4,
    "eave_height_m": 4.0,
    "ridge_height_m": 4.8,
    "spans": 1,
    "bays": 3,
    "rows": 2,
    "plants_per_row": 16,
    "plant_pitch_m": 0.5,
    "row_spacing_m": 1.6,
    "support_height_m": 0.3,
    "crop_model": "simple",
    "variety": "cherry_tomato",
}


class BasicSetup(BaseModel):
    """The values of the builder's first form, in metres. Each field's title
    is the form's label for it, and the schema's example the house the form
    starts from."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra={"examples": [STARTING_HOUSE]}
    )

    installation_id: ItemId = Field(title="Identifier")
    name: str = Field(min_length=1, title="Name")
    length_m: PositiveFloat = Field(title="Length (m)")
    width_m: PositiveFloat = Field(title="Width (m)")
    eave_height_m: PositiveFloat = Field(title="Height to the gutters (m)")
    ridge_height_m: PositiveFloat = Field(title="Height to the ridge (m)")
    spans: PositiveInt = Field(default=1, title="Spans")
    bays: PositiveInt = Field(default=1, title="Bays")
    rows: PositiveInt = Field(title="Crop rows")
    plants_per_row: PositiveInt = Field(title="Plants per row")
    plant_pitch_m: PositiveFloat = Field(title="Between plants (m)")
    row_spacing_m: PositiveFloat = Field(title="Between rows (m)")
    support_height_m: PositiveFloat = Field(title="Gutter height (m)")
    crop_model: CropModel = Field(title="Crop model")
    variety: str = Field(min_length=1, title="Variety")


def basic_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema of the first form's values, published as
    `basic.schema.json`: what a client sends, so that a field with a default
    may be left out."""
    return {"$schema": JSON_SCHEMA_DIALECT, **BasicSetup.model_json_schema()}


def basic_installation(values: BasicSetup) -> Installation:
    """The draft the form's values describe: the rows, on tomato gutters at
    the height asked, centred in the house's plan, every row growing the
    crop chosen. Nothing else is placed, no door, vent or equipment, which
    the assessment then reports missing."""
    along = (values.plants_per_row - 1) * values.plant_pitch_m
    across = (values.rows - 1) * values.row_spacing_m
    return Installation(
        installation_id=values.installation_id,
        name=values.name,
        envelope=Envelope(
            length=values.length_m,
            width=values.width_m,
            eave_height=values.eave_height_m,
            ridge_height=values.ridge_height_m,
            spans=values.spans,
            bays=values.bays,
        ),
        layout=Layout(
            crop_rows=CropRows(
                origin=Point2(x=(values.length_m - along) / 2, y=(values.width_m - across) / 2),
                rows=values.rows,
                positions_per_row=values.plants_per_row,
                plant_pitch=values.plant_pitch_m,
                row_spacing=values.row_spacing_m,
                # Checked as any support is: too low a gutter is refused.
                support=RowSupport.model_validate(
                    TOMATO_GUTTER.model_dump() | {"height": values.support_height_m}
                ),
            )
        ),
        row_crops=[
            RowCrop(row=row, crop_model=values.crop_model, variety=values.variety)
            for row in range(1, values.rows + 1)
        ],
    )
