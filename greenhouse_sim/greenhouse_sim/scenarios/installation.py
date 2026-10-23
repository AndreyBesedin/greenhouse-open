"""An installation: the house part of a scenario (decision 0050).

Its envelope, its layout and the crop each row grows, as a scenario's
manifest holds them (format 4, `manifest_files`) and the setup builder
edits them (`greenhouse_sim.builder`). A value no greenhouse can have is
refused as the models refuse it. What only the parts together get wrong,
such as a row reaching through a wall, is the builder's assessment instead,
so that a draft can be kept and edited until it can run.

A run grows one crop model and one variety, over its layout's rows times
their planting positions (`ScenarioConfig`): `scenario_house` gives a
scenario those fields from its installation, and refuses an installation a
run cannot grow yet; `scenario_installation` gives the installation back
from a scenario whose crop fills its layout's rows.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationInfo, field_validator

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.identifiers import ItemId
from greenhouse_sim.world.layout import Layout

if TYPE_CHECKING:
    # Typed only: the configuration's module reads manifests, which hold
    # installations.
    from greenhouse_sim.scenarios.config import ScenarioConfig


class RowCrop(BaseModel):
    """The crop one row grows: its model and its variety. Rows are numbered
    from 1, as `CropRows` numbers them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    row: PositiveInt
    crop_model: CropModel
    variety: str = Field(min_length=1)


class Installation(BaseModel):
    """A greenhouse as authored: no weather, period, control or policy,
    which are a scenario's."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    installation_id: ItemId
    name: str = Field(min_length=1)
    envelope: Envelope
    layout: Layout
    row_crops: list[RowCrop] = []

    # The layout's items and the envelope's doors and vents are named apart,
    # as each of them names its own: an edit or a command names one item.
    @field_validator("layout")
    @classmethod
    def _named_apart_from_the_doors_and_vents(cls, layout: Layout, info: ValidationInfo) -> Layout:
        envelope = info.data.get("envelope")
        if not isinstance(envelope, Envelope) or not envelope.openings:
            return layout
        named = (
            {fixture.fixture_id for fixture in layout.fixtures()}
            | {zone.zone_id for zone in layout.zones}
            | {piece.actuator_id for piece in layout.equipment}
            | {sensor.sensor_id for sensor in layout.sensors}
        )
        shared = sorted(named & {opening.opening_id for opening in envelope.openings})
        if shared:
            raise ValueError(
                f"the layout and the envelope's doors and vents share an identifier: "
                f"{', '.join(shared)}"
            )
        return layout

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


class CannotRun(ValueError):
    """An installation a run cannot grow yet, and why."""


class CannotCopy(ValueError):
    """A scenario whose house an installation cannot hold as it is, and why."""


class ScenarioHouse(BaseModel):
    """The fields of a scenario its installation gives: its house, and its
    crop as `ScenarioConfig` holds it, the layout's rows times their
    planting positions, every one growing one model and one variety."""

    model_config = ConfigDict(frozen=True)

    envelope: Envelope
    layout: Layout
    rows: PositiveInt
    columns: PositiveInt
    crop_model: CropModel
    variety: str


def scenario_house(installation: Installation) -> ScenarioHouse:
    """What a scenario's run grows in an installation: its rows of planting
    positions, each row growing the one crop all of them grow. Refused if
    its layout has no crop rows, a row has no crop, or rows grow different
    crops, which a run cannot grow yet (P12.5)."""
    rows = installation.layout.crop_rows
    if rows is None:
        raise CannotRun("it has no crop rows")
    chosen = {crop.row for crop in installation.row_crops}
    bare = [row for row in range(1, rows.rows + 1) if row not in chosen]
    if bare:
        raise CannotRun(f"rows {bare} have no crop")
    crops = sorted({(crop.crop_model, crop.variety) for crop in installation.row_crops})
    if len(crops) > 1:
        grown = ", ".join(f"{model.value} {variety}" for model, variety in crops)
        raise CannotRun(f"its rows grow different crops ({grown}); a run grows one")
    ((crop_model, variety),) = crops
    return ScenarioHouse(
        envelope=installation.envelope,
        layout=installation.layout,
        rows=rows.rows,
        columns=rows.positions_per_row,
        crop_model=crop_model,
        variety=variety,
    )


def scenario_installation(config: ScenarioConfig) -> Installation:
    """A scenario's house as an installation, named as the scenario is: its
    envelope, its layout, and every crop row growing the scenario's crop.
    Refused if the scenario plants fewer positions than its layout's rows
    hold: an installation's crop grows every position of a row, and the
    copy would plant them all."""
    crop_rows = config.layout.crop_rows
    if crop_rows is not None and (config.rows, config.columns) != (
        crop_rows.rows,
        crop_rows.positions_per_row,
    ):
        raise CannotCopy(
            f"its crop of {config.rows} rows of {config.columns} plants does not fill "
            f"its layout's {crop_rows.rows} rows of {crop_rows.positions_per_row} positions, "
            "as an installation's crop does"
        )
    rows = 0 if crop_rows is None else crop_rows.rows
    return Installation(
        installation_id=config.greenhouse_id,
        name=config.name,
        envelope=config.envelope,
        layout=config.layout,
        row_crops=[
            RowCrop(row=row, crop_model=config.crop_model, variety=config.variety)
            for row in range(1, rows + 1)
        ],
    )
