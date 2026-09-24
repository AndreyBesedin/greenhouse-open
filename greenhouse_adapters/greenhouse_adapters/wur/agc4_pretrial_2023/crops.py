"""CropMeasurements.xlsx -> plants and plant-level Observations.

Sheet `All data` holds one row per labelled measurement plant per week: 40
plants (labels 41-80) on nine weekly dates from 6 September to 1 November
2023, each plant in one of eight treatment fields (Cherry, EC3 or EC6, high /
medium / low / no light) with repetition 1-5. The per-week sheets repeat the
same values.

Measurements are manual (ruler, visual counts) and dated without a time, so
they are pinned to local noon. Flower and fruit counts cover the oldest five
trusses. The sheet's own sum columns count a blank truss cell as zero - 86
rows with no flowering cell measured still show a sum of 0 - so sums are
computed here from measured cells only and omitted when none was measured.
Coloured fruit is split into yellow / orange / red only in weeks 43-44; the
earlier coloration columns cannot tell a blank from a zero, so red and
coloured counts are emitted only where the split was measured.

Plant identity follows the label, with one recorded exception: in week 40
label 47's measurement plant was replaced by a representative plant
("Original measurement plant was without a dripper"), so from that week
label 47 is a different plant.

The Plant model needs a row and a position; for these plants they are the
dataset's own field (9-16) and repetition (1-5) numbers, not coordinates.
The zone names the light and EC treatment."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import IO

import openpyxl
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.greenhouse import Plant
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_adapters.wur.agc4_pretrial_2023 import SOURCE_ID
from greenhouse_adapters.wur.agc4_pretrial_2023.compartments import COMPARTMENT_ID, GREENHOUSE_ID
from greenhouse_adapters.wur.common.cells import number_cell
from greenhouse_adapters.wur.common.time import local_noon

SHEET = "All data"
SOURCE = RecordSource(type=SourceType.IMPORTED_DATA, source_id=SOURCE_ID)

# label -> first week whose rows describe a replacement plant
REPLACED_FROM_WEEK: dict[int, int] = {47: 40}

_SINGLE_VALUE_COLUMNS: dict[str, ObservationType] = {
    "Plantheigth": ObservationType.PLANT_HEIGHT_CM,
    "# leaves": ObservationType.LEAF_COUNT,
    "leaf length": ObservationType.LEAF_LENGTH_CM,
    "leaf width": ObservationType.LEAF_WIDTH_CM,
    "#trusses": ObservationType.TRUSS_COUNT,
}
_IDENTITY_COLUMNS = (
    "Date",
    "Week",
    "# on label",
    "Variety",
    "Corrected EC",
    "Light",
    "field",
    "Plant repetition#",
)
_TRUSS_KINDS = ("flowering", "set", "yellow", "orange", "red")
_TRUSS_COLUMN = re.compile(r"#\s*(flowering|set|yellow|orange|red|coloration)\s*trus\s*(\d)?\s*$")
_TRUSSES = 5


@dataclass(frozen=True)
class CropMeasurements:
    plants: list[Plant]
    observations: list[Observation]


def read_crop_measurements(source: IO[bytes]) -> CropMeasurements:
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        rows = workbook[SHEET].iter_rows(values_only=True)
        header = [str(cell).strip() if cell is not None else "" for cell in next(rows)]
        missing = sorted({*_IDENTITY_COLUMNS, *_SINGLE_VALUE_COLUMNS} - set(header))
        if missing:
            raise ValueError(f"{SHEET} is missing columns {missing}")
        index = {name: position for position, name in enumerate(header)}
        trusses = _truss_columns(header)

        plants: dict[str, Plant] = {}
        observations: list[Observation] = []
        for row in rows:
            if all(cell is None for cell in row):
                continue
            label = _whole_number(row, index["# on label"])
            day = _day(row, index["Date"])
            plant = _plant(label, _whole_number(row, index["Week"]), row, index)
            if plants.setdefault(plant.plant_id, plant) != plant:
                raise ValueError(f"{SHEET}: plant {plant.plant_id} changes treatment between weeks")
            timestamp = local_noon(day)
            stem = f"wur23_{plant.plant_id}_{day:%Y%m%d}"
            for observation_type, value in _values(row, index, trusses):
                observations.append(
                    Observation(
                        observation_id=f"{stem}_{observation_type.value}",
                        greenhouse_id=GREENHOUSE_ID,
                        compartment_id=COMPARTMENT_ID,
                        plant_id=plant.plant_id,
                        timestamp=timestamp,
                        observation_type=observation_type,
                        value=value,
                        source=SOURCE,
                    )
                )
        return CropMeasurements(
            plants=sorted(plants.values(), key=lambda p: p.plant_id), observations=observations
        )
    finally:
        workbook.close()


def _plant(label: int, week: int, row: tuple[object, ...], index: dict[str, int]) -> Plant:
    replaced_from = REPLACED_FROM_WEEK.get(label)
    suffix = "b" if replaced_from is not None and week >= replaced_from else ""
    light = _text(row, index["Light"])
    ec = _text(row, index["Corrected EC"])
    return Plant(
        plant_id=f"wur23_p{label}{suffix}",
        variety=_text(row, index["Variety"]).lower(),
        row=_whole_number(row, index["field"]),
        position_in_row=_whole_number(row, index["Plant repetition#"]),
        zone=f"{light} / {ec}",
    )


def _values(
    row: tuple[object, ...], index: dict[str, int], trusses: dict[str, list[int]]
) -> Iterator[tuple[ObservationType, float]]:
    for column, observation_type in _SINGLE_VALUE_COLUMNS.items():
        value = number_cell(row, index[column])
        if value is not None:
            yield observation_type, value
    measured = {kind: _measured(row, trusses[kind]) for kind in _TRUSS_KINDS}
    if measured["flowering"]:
        yield ObservationType.OPEN_FLOWER_COUNT, sum(measured["flowering"])
    if measured["set"]:
        yield ObservationType.GREEN_FRUIT_COUNT, sum(measured["set"])
    if measured["red"]:
        yield ObservationType.RIPE_FRUIT_COUNT, sum(measured["red"])
    coloured = measured["yellow"] + measured["orange"] + measured["red"]
    if coloured:
        yield ObservationType.COLOURED_FRUIT_COUNT, sum(coloured)


def _truss_columns(header: list[str]) -> dict[str, list[int]]:
    """Column positions per count kind, in truss order. One header in the
    real sheet ('#  red trus') has no truss number; it takes the number of
    the column before it, which is always the same truss's orange count."""
    columns: dict[str, dict[int, int]] = {kind: {} for kind in _TRUSS_KINDS}
    previous_truss: int | None = None
    for position, name in enumerate(header):
        match = _TRUSS_COLUMN.match(name)
        if match is None:
            continue
        kind, number = match.group(1), match.group(2)
        truss = int(number) if number is not None else previous_truss
        if truss is None:
            raise ValueError(f"{SHEET}: cannot tell which truss column {name!r} counts")
        previous_truss = truss
        if kind in columns:
            columns[kind][truss] = position
    for kind, by_truss in columns.items():
        if sorted(by_truss) != list(range(1, _TRUSSES + 1)):
            raise ValueError(
                f"{SHEET}: expected {kind} counts for trusses 1-5, found {sorted(by_truss)}"
            )
    return {
        kind: [by_truss[t] for t in range(1, _TRUSSES + 1)] for kind, by_truss in columns.items()
    }


def _measured(row: tuple[object, ...], positions: list[int]) -> list[float]:
    return [value for position in positions if (value := number_cell(row, position)) is not None]


def _whole_number(row: tuple[object, ...], position: int) -> int:
    value = number_cell(row, position)
    if value is None or value != int(value):
        raise ValueError(f"{SHEET}: expected a whole number, found {row[position]!r}")
    return int(value)


def _text(row: tuple[object, ...], position: int) -> str:
    cell = row[position] if position < len(row) else None
    if not isinstance(cell, str) or not cell.strip():
        raise ValueError(f"{SHEET}: expected text, found {cell!r}")
    return cell.strip()


def _day(row: tuple[object, ...], position: int) -> date:
    cell = row[position] if position < len(row) else None
    if not isinstance(cell, datetime):
        raise ValueError(f"{SHEET}: expected a date, found {cell!r}")
    return cell.date()
