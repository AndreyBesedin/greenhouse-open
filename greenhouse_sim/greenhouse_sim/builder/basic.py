"""The form's first step: a simple pitched greenhouse with parallel rows."""

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt

from greenhouse_sim.builder.installation import InstallationDraft, RowCrop
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Point2
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import TOMATO_GUTTER, CropRows, RowSupport


class BasicSetup(BaseModel):
    """Only values a person can reasonably fill in before seeing a preview."""

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
    model_id: ItemId
    variety: str = Field(min_length=1)


def basic_installation(values: BasicSetup) -> InstallationDraft:
    """Build, using exactly the geometry the simulator already understands.

    Plant rows are centred in plan, leaving any extra space for paths and
    equipment. No openings or equipment are silently invented.
    """
    envelope = Envelope(
        length=values.length_m,
        width=values.width_m,
        eave_height=values.eave_height_m,
        ridge_height=values.ridge_height_m,
        spans=values.spans,
        bays=values.bays,
    )
    support = RowSupport.model_validate(
        TOMATO_GUTTER.model_dump() | {"height": values.support_height_m}
    )
    along = (values.plants_per_row - 1) * values.plant_pitch_m
    across = (values.rows - 1) * values.row_spacing_m
    layout = Layout(
        crop_rows=CropRows(
            origin=Point2(x=(values.length_m - along) / 2, y=(values.width_m - across) / 2),
            rows=values.rows,
            positions_per_row=values.plants_per_row,
            plant_pitch=values.plant_pitch_m,
            row_spacing=values.row_spacing_m,
            support=support,
        )
    )
    return InstallationDraft(
        installation_id=values.installation_id,
        name=values.name,
        envelope=envelope,
        layout=layout,
        row_crops=[
            RowCrop(row=index, model_id=values.model_id, variety=values.variety)
            for index in range(1, values.rows + 1)
        ],
    )
