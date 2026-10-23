"""A first draft from a few values a person fills in before any preview:
a pitched house of equal spans and bays, and parallel rows of one crop
(P12.0)."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    ValidationInfo,
    field_validator,
)

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.installation import Installation, RowCrop
from greenhouse_sim.world.envelope import (
    HIGHEST_M,
    LONGEST_SIDE_M,
    MOST_BAYS,
    MOST_SPANS,
    MOST_SPANS_BY_BAYS,
    Envelope,
)
from greenhouse_sim.world.geometry import Point2
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import (
    MOST_PLANTING_POSITIONS,
    MOST_POSITIONS_PER_ROW,
    MOST_ROWS,
    TOMATO_GUTTER,
    CropRows,
    RowSupport,
)


class BasicSetup(BaseModel):
    """The values of the builder's first form, in metres. Each is checked
    as the envelope and the rows check what it becomes, before either is
    made, so that a value refused is refused by the form's own field: their
    bounds, and their rules between two values, held by the second."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    installation_id: ItemId
    name: str = Field(min_length=1)
    length_m: PositiveFloat = Field(le=LONGEST_SIDE_M)
    width_m: PositiveFloat = Field(le=LONGEST_SIDE_M)
    eave_height_m: PositiveFloat = Field(le=HIGHEST_M)
    ridge_height_m: PositiveFloat = Field(le=HIGHEST_M)
    spans: PositiveInt = Field(default=1, le=MOST_SPANS)
    bays: PositiveInt = Field(default=1, le=MOST_BAYS)
    rows: PositiveInt = Field(le=MOST_ROWS)
    plants_per_row: PositiveInt = Field(le=MOST_POSITIONS_PER_ROW)
    plant_pitch_m: PositiveFloat
    row_spacing_m: PositiveFloat
    # A tomato gutter's top, above its depth.
    support_height_m: float = Field(gt=TOMATO_GUTTER.depth)
    crop_model: CropModel
    variety: str = Field(min_length=1)

    @field_validator("ridge_height_m")
    @classmethod
    def _ridge_is_not_below_the_eaves(cls, ridge: float, info: ValidationInfo) -> float:
        eaves = info.data.get("eave_height_m")
        if eaves is not None and ridge < eaves:
            raise ValueError(f"the ridge ({ridge} m) is below the eaves ({eaves} m)")
        return ridge

    @field_validator("bays")
    @classmethod
    def _not_too_many_bays_and_spans(cls, bays: int, info: ValidationInfo) -> int:
        spans = info.data.get("spans")
        if spans is not None and spans * bays > MOST_SPANS_BY_BAYS:
            raise ValueError(
                f"{spans} spans of {bays} bays; a greenhouse has at most "
                f"{MOST_SPANS_BY_BAYS} of them"
            )
        return bays

    @field_validator("plants_per_row")
    @classmethod
    def _not_too_many_plants(cls, plants: int, info: ValidationInfo) -> int:
        rows = info.data.get("rows")
        if rows is not None and rows * plants > MOST_PLANTING_POSITIONS:
            raise ValueError(
                f"{rows} rows of {plants} plants; a crop has at most "
                f"{MOST_PLANTING_POSITIONS} of them"
            )
        return plants

    @field_validator("row_spacing_m")
    @classmethod
    def _gutters_do_not_overlap(cls, spacing: float, info: ValidationInfo) -> float:
        rows = info.data.get("rows")
        if rows is not None and rows > 1 and spacing < TOMATO_GUTTER.width:
            raise ValueError(
                f"rows {spacing} m apart are too close for gutters {TOMATO_GUTTER.width} m wide"
            )
        return spacing


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
