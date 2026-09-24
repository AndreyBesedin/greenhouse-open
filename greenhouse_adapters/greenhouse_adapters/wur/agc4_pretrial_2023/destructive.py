"""DestructiveHarvest.xlsx -> DESTRUCTIVE_SAMPLE events.

Sheet `All Data` (its header is the row that names `Sample name`) holds the
destructively harvested sample plants of four dates: 4 September 2023 at
transplant, 18 September (switch to the generative phase), 29 September
(fruit set) and 9 November (end product). These are not the 40 labelled
measurement plants: a sample plant is removed when it is measured, so it has
no history and no plant identity here.

The 4 September samples were taken before any treatment started, yet `All
Data` lists each of them once per treatment: 96 rows that are 12 plants, each
copied under eight treatment-coded names with identical measurements (the
first harvest sheet has the same 12). Untreated samples with identical values
on one date are therefore kept once, as `untreated_<sample number>`, with the
names they were listed as. The three later dates have 48 treated samples
each, so the dataset holds 156 samples.

Each sample becomes one compartment-level event dated at local noon, carrying
its phase, days after sowing, treatment and every measured value as
parameters; `N/A` and empty cells are left out. It is its own event type, not
HARVEST: the fresh weights are biomass sampled for analysis, not yield, and
must never add up to harvested mass.

Values are kept as recorded, including physically impossible ones: sample
Cherry_EC3_ML_3 on 18 September 2023 lists 1287.85 g of dry flowers on a
19.17 g plant, probably a misplaced decimal point. Correcting source data is
a consumer's decision, made visibly, not an adapter's."""

import re
from datetime import date, datetime
from typing import IO, Any

import openpyxl
from greenhouse_protocol.enums import EventSource, EventType
from greenhouse_protocol.event import Event

from greenhouse_adapters.wur.agc4_pretrial_2023.compartments import COMPARTMENT_ID, GREENHOUSE_ID
from greenhouse_adapters.wur.common.cells import number_cell
from greenhouse_adapters.wur.common.time import local_noon

SHEET = "All Data"
SAMPLE_NAME_COLUMN = "Sample name"
UNTREATED = "No treatment"
_TEXT_PARAMETERS = {
    "Phase": "phase",
    "Treatment": "treatment",
    "Variety": "variety",
    "EC": "ec",
    "Light": "light",
}
_NAMED_NUMBERS = {
    "DAS": "days_after_sowing",
    "Plant density (p/m2)": "plant_density_per_m2",
    "Sample n": "sample_number",
}
_REQUIRED = ("Date", SAMPLE_NAME_COLUMN, *_TEXT_PARAMETERS, *_NAMED_NUMBERS)
# what differs between the copies of one untreated sample
_COPY_LABELS = frozenset({"sample_name", "ec", "light"})

_Sample = tuple[date, dict[str, Any]]


def read_destructive_samples(source: IO[bytes]) -> list[Event]:
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        samples = _read_rows(workbook[SHEET].iter_rows(values_only=True))
    finally:
        workbook.close()

    events = [_event(day, parameters) for day, parameters in _collapse_untreated_copies(samples)]
    ids = [event.event_id for event in events]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"{SHEET}: sample names repeat on the same date: {duplicates[:5]}")
    return events


def parameter_name(header: str) -> str:
    """'FW leaves (g/plant)' -> 'fw_leaves_g_per_plant': a stable parameter
    key that keeps the unit."""
    text = header.lower().replace("cm²", "cm2")
    for unit, spelled in (
        ("#/plant", "count per plant"),
        ("/plant", " per plant"),
        ("/g", " per g"),
    ):
        text = text.replace(unit, spelled)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _read_rows(rows: Any) -> list[_Sample]:
    header: list[str] | None = None
    for row in rows:
        if any(isinstance(cell, str) and cell.strip() == SAMPLE_NAME_COLUMN for cell in row):
            header = [str(cell).strip() if cell is not None else "" for cell in row]
            break
    if header is None:
        raise ValueError(f"{SHEET} has no header row naming {SAMPLE_NAME_COLUMN!r}")
    missing = sorted(set(_REQUIRED) - set(header))
    if missing:
        raise ValueError(f"{SHEET} is missing columns {missing}")
    index = {name: position for position, name in enumerate(header) if name}
    measured = [
        (position, parameter_name(name))
        for name, position in index.items()
        if name not in _REQUIRED
    ]

    samples: list[_Sample] = []
    for row in rows:
        if all(cell is None for cell in row):
            continue
        parameters: dict[str, Any] = {"sample_name": _text(row, index[SAMPLE_NAME_COLUMN])}
        for column, key in _TEXT_PARAMETERS.items():
            parameters[key] = _text(row, index[column])
        for column, key in _NAMED_NUMBERS.items():
            value = number_cell(row, index[column])
            if value is not None:
                parameters[key] = value
        for position, key in measured:
            value = _measurement(row, position)
            if value is not None:
                parameters[key] = value
        samples.append((_day(row, index["Date"]), parameters))
    return samples


def _collapse_untreated_copies(samples: list[_Sample]) -> list[_Sample]:
    """One entry per physical sample: untreated rows that agree on everything
    but their treatment-coded name, EC and light are the same plant."""
    kept: list[_Sample] = []
    untreated: dict[tuple[Any, ...], dict[str, Any]] = {}
    for day, parameters in samples:
        if parameters["treatment"] != UNTREATED:
            kept.append((day, parameters))
            continue
        identity = tuple(sorted((k, v) for k, v in parameters.items() if k not in _COPY_LABELS))
        key = (day, identity)
        if key in untreated:
            untreated[key]["listed_as"].append(parameters["sample_name"])
            continue
        merged = {k: v for k, v in parameters.items() if k not in _COPY_LABELS}
        merged["listed_as"] = [parameters["sample_name"]]
        untreated[key] = merged
        kept.append((day, merged))

    for parameters in untreated.values():
        parameters["listed_as"] = sorted(parameters["listed_as"])
        number = parameters.get("sample_number")
        parameters["sample_name"] = (
            f"untreated_{int(number)}" if number is not None else parameters["listed_as"][0]
        )
    return kept


def _event(day: date, parameters: dict[str, Any]) -> Event:
    return Event(
        event_id=f"wur23_sample_{day:%Y%m%d}_{parameters['sample_name']}",
        greenhouse_id=GREENHOUSE_ID,
        compartment_id=COMPARTMENT_ID,
        plant_id=None,
        timestamp=local_noon(day),
        event_type=EventType.DESTRUCTIVE_SAMPLE,
        source=EventSource.HUMAN_REPORTED,
        parameters=parameters,
    )


def _measurement(row: tuple[object, ...], position: int) -> float | None:
    cell = row[position] if position < len(row) else None
    if isinstance(cell, str) and cell.strip().upper() == "N/A":
        return None
    return number_cell(row, position)


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
