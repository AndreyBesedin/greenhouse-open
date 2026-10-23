"""A first draft from a few values a person fills in before any preview:
a pitched house of equal spans and bays, and parallel rows of one crop
(P12.0)."""

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.installation import Installation, RowCrop
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Point2
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import TOMATO_GUTTER, CropRows, RowSupport


class BasicSetup(BaseModel):
    """The values of the builder's first form, in metres."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    installation_id: ItemId
    name: str = Field(min_length=1)
    length_m: PositiveFloat
    width_m: PositiveFloat
    eave_height_m: PositiveFloat
    ridge_height_m: PositiveFloat
    spans: PositiveInt = 1
    bays: PositiveInt = 1
    rows: PositiveInt
    plants_per_row: PositiveInt
    plant_pitch_m: PositiveFloat
    row_spacing_m: PositiveFloat
    support_height_m: PositiveFloat
    crop_model: CropModel
    variety: str = Field(min_length=1)


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
