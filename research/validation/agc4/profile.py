"""Profiles the two AGC4 archives as the adapters keep them: what each file
holds, never the data itself (item 5 of the research priorities, step 2 of
the AGC4 memo's next steps).

    python -m research.validation.agc4.profile [--data-dir DIR] \
        > research/validation/agc4/profile.json

It reads the time-series archive of each record where `greenhouse-data
prepare wur agc4-2024 --profile dev` (and `agc4-2023`) put it, checked
against its manifest's checksum, and writes JSON:

- for each CSV of the 2024 archive (a team's compartment, the weather, the
  forecast): its rows, its first and last timestamp as recorded, its most
  common step, and for each column the rows that hold a value, the share
  that do not, and, for a column of a few values, which;
- for each sheet of its `Harvest.xlsx`: the columns of its header and the
  plants per compartment; on a final harvest's sheet, the plants whose fruit
  were sorted green and red, those weighed for red fruit alone, and each
  batch of fruit dried, with its fresh and dry weight;
- for the 2023 archive's `ClimateTimeseries.xlsx`, the same as for a 2024
  CSV; for its other workbooks, each sheet's rows and columns.

A cell that is empty, or holds `NaN`, holds no value.
"""

import argparse
import csv
import io
import itertools
import json
import math
import re
import sys
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import openpyxl
from greenhouse_adapters.manifests import load_manifest
from greenhouse_adapters.storage.layout import DataDirectory

from research.validation.agc4.archives import (
    CHALLENGE,
    CHALLENGE_ARCHIVE,
    PRETRIAL,
    PRETRIAL_ARCHIVE,
    PRETRIAL_CLIMATE,
    PRETRIAL_CLIMATE_SHEET,
    archive_path,
    holds,
    members,
    provenance,
)

HARVEST_WORKBOOK: Final = "Harvest.xlsx"
# The pre-trial's climate sheet stamps each row in this column, in local
# time; it and the other two say the same moment, and are not profiled.
PRETRIAL_TIME_COLUMN: Final = "date"
PRETRIAL_STAMPS: Final = frozenset({"datenum", PRETRIAL_TIME_COLUMN, "time"})
# A column with no more values than this lists them: states, flags and steps.
FEW_VALUES: Final = 10
SHARE_DIGITS: Final = 4
GRAMS_DIGITS: Final = 2
# A sample plant's label: compartment 3.02's 17th plant is "302-17".
PLANT: Final = re.compile(r"^(\d)(\d{2})-\d+$")
FINAL_HARVEST: Final = "final harvest"
# The row of a final harvest's sheet that starts the fruit dried: fresh
# weights on it, dry weights on the next row, the sheet's own dry matter
# percentage on the one after.
DRYING: Final = "drying"
# A final harvest's columns, by their header with its spaces taken out and
# lower-cased, as the sheets spell them differently: per colour, the column
# that counts the fruit and the one that weighs them fresh.
FRUIT_COLUMNS: Final = {
    "green": ("#tomgreen", "fwgreen"),
    "red": ("#tomred", "fwred"),
}
WHOLE_PLANT: Final = "fwtot"

# A part of the profile, as JSON writes it.
type Profile = dict[str, Any]
INDENT: Final = " "


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=None, help="override GREENHOUSE_DATA_DIR")
    arguments = parser.parse_args(argv)
    data = DataDirectory(arguments.data_dir)
    profile = {
        CHALLENGE: {
            **provenance(load_manifest(CHALLENGE), CHALLENGE_ARCHIVE),
            **profile_challenge(archive_path(data, CHALLENGE, CHALLENGE_ARCHIVE)),
        },
        PRETRIAL: {
            **provenance(load_manifest(PRETRIAL), PRETRIAL_ARCHIVE),
            **profile_pretrial(archive_path(data, PRETRIAL, PRETRIAL_ARCHIVE)),
        },
    }
    sys.stdout.write(written(profile) + "\n")
    return 0


def written(value: object, depth: int = 0) -> str:
    """The profile as JSON, an object of plain values on a line of its own,
    such as a column's counts, so that a change to the profile reads as the
    lines of what changed."""
    if not isinstance(value, dict) or all(_plain(each) for each in value.values()):
        return json.dumps(value, ensure_ascii=False)
    inner = INDENT * (depth + 1)
    lines = [
        f"{inner}{json.dumps(key, ensure_ascii=False)}: {written(each, depth + 1)}"
        for key, each in value.items()
    ]
    return "{\n" + ",\n".join(lines) + "\n" + INDENT * depth + "}"


def profile_challenge(archive: Path) -> Profile:
    """The 2024 archive: its CSVs, and its harvest workbook's sheets."""
    with zipfile.ZipFile(archive) as opened:
        names = members(opened)
        tables = {
            Path(name).name: _profile_csv(opened.read(name))
            for name in names
            if name.endswith(".csv")
        }
        (harvest,) = [name for name in names if Path(name).name == HARVEST_WORKBOOK]
        workbook = openpyxl.load_workbook(io.BytesIO(opened.read(harvest)), data_only=True)
    return {"time_series": tables, "harvest": _profile_harvest(workbook)}


def profile_pretrial(archive: Path) -> Profile:
    """The 2023 archive: its climate sheet as a table, every other sheet's size."""
    workbooks: Profile = {}
    with zipfile.ZipFile(archive) as opened:
        for name in members(opened):
            if not name.endswith(".xlsx"):
                continue
            book = openpyxl.load_workbook(io.BytesIO(opened.read(name)), data_only=True)
            sheets: Profile = {}
            for sheet in book.worksheets:
                rows = [row for row in sheet.iter_rows(values_only=True) if _any(row)]
                sheets[sheet.title] = {
                    "rows": len(rows),
                    "columns": max((_width(row) for row in rows), default=0),
                }
            workbooks[Path(name).name] = {"sheets": sheets}
            if Path(name).name == PRETRIAL_CLIMATE:
                rows = list(book[PRETRIAL_CLIMATE_SHEET].iter_rows(values_only=True))
                header = [str(cell) for cell in rows[0]]
                workbooks[Path(name).name]["climate"] = _profile_table(
                    header, rows[1:], _stamped_by(header.index(PRETRIAL_TIME_COLUMN))
                )
    return {"workbooks": workbooks}


def _profile_csv(content: bytes) -> Profile:
    reader = csv.reader(io.StringIO(content.decode("utf-8")))
    header = next(reader)
    return _profile_table(header, list(reader), lambda row: datetime.fromisoformat(str(row[0])))


def _profile_table(
    header: Sequence[str],
    rows: Sequence[Sequence[object]],
    stamp: Callable[[Sequence[object]], datetime],
) -> Profile:
    """A table stamped by its first column (or by `stamp`): its rows, its
    span, its most common step, and how full each other column is."""
    times = [stamp(row) for row in rows]
    steps = Counter(int((later - earlier).total_seconds()) for earlier, later in _pairs(times))
    columns: Profile = {}
    for index, name in enumerate(header):
        if index == 0 or name in PRETRIAL_STAMPS:
            continue
        values = [row[index] for row in rows if index < len(row) and holds(row[index])]
        column: Profile = {
            "present": len(values),
            "missing_share": round(1 - len(values) / len(rows), SHARE_DIGITS) if rows else 1.0,
        }
        distinct = {_number_or_text(value) for value in values}
        if len(distinct) <= FEW_VALUES:
            column["values"] = sorted(distinct, key=str)
        columns[name] = column
    return {
        "rows": len(rows),
        "first": times[0].isoformat() if times else None,
        "last": times[-1].isoformat() if times else None,
        "step_s": steps.most_common(1)[0][0] if steps else None,
        "columns": columns,
    }


def _profile_harvest(workbook: openpyxl.Workbook) -> Profile:
    sheets: Profile = {}
    for sheet in workbook.worksheets:
        rows = [row for row in sheet.iter_rows(values_only=True) if _any(row)]
        plants = Counter(code for row in rows if (code := _compartment(row)) is not None)
        profile: Profile = {
            "header": [str(cell).strip() for cell in rows[0] if cell is not None] if rows else [],
            "plants": dict(sorted(plants.items())),
        }
        if sheet.title.strip().lower().startswith(FINAL_HARVEST):
            profile.update(_final_harvest(rows))
        sheets[sheet.title] = profile
    return {"sheets": sheets}


def _final_harvest(rows: Sequence[Sequence[object]]) -> Profile:
    """Of a final harvest's sheet: the plants sorted by colour, those weighed
    for red fruit alone, the red fruit's mean fresh weight per plant over
    each, and the batches dried."""
    columns = {_key(cell): index for index, cell in enumerate(rows[0]) if cell is not None}
    whole, red = columns[WHOLE_PLANT], columns[FRUIT_COLUMNS["red"][1]]
    plants = [row for row in rows if _compartment(row) is not None]
    sorted_by_colour = [row for row in plants if _number(_at(row, whole)) is not None]
    red_alone = [
        row
        for row in plants
        if _number(_at(row, whole)) is None and _number(_at(row, red)) is not None
    ]
    dried: list[Profile] = []
    for index, row in enumerate(rows):
        if str(row[0]).strip().lower() != DRYING:
            continue
        dry_row, percent_row = rows[index + 1], rows[index + 2]
        for colour, (count, fresh) in FRUIT_COLUMNS.items():
            fresh_g = _number(_at(row, columns[fresh]))
            dry_g = _number(_at(dry_row, columns[fresh]))
            if fresh_g is None or dry_g is None:
                continue
            sheet_percent = _number(_at(percent_row, columns[fresh]))
            dried.append(
                {
                    "fruit": colour,
                    "fruits": _number(_at(row, columns[count])),
                    "fresh_g": round(fresh_g, GRAMS_DIGITS),
                    "dry_g": round(dry_g, GRAMS_DIGITS),
                    "dry_matter_percent": round(100 * dry_g / fresh_g, GRAMS_DIGITS),
                    "sheet_percent": None
                    if sheet_percent is None
                    else round(sheet_percent, GRAMS_DIGITS),
                }
            )
    return {
        "sorted_by_colour": len(sorted_by_colour),
        "red_alone": len(red_alone),
        "red_fresh_g_per_plant": {
            "every_plant": _mean_of(plants, red),
            "sorted_by_colour": _mean_of(sorted_by_colour, red),
        },
        "dried": dried,
    }


def _mean_of(rows: Sequence[Sequence[object]], column: int) -> float | None:
    """The mean of a column over the rows that hold a number in it."""
    numbers = [number for row in rows if (number := _number(_at(row, column))) is not None]
    return round(sum(numbers) / len(numbers), GRAMS_DIGITS) if numbers else None


def _compartment(row: Sequence[object]) -> str | None:
    for cell in row:
        found = PLANT.match(str(cell).strip()) if isinstance(cell, str) else None
        if found is not None:
            return f"{found[1]}.{found[2]}"
    return None


def _plain(value: object) -> bool:
    """Whether a value is written on its parent's line: not an object, nor a
    list holding one."""
    if isinstance(value, dict):
        return False
    return not isinstance(value, list) or not any(isinstance(each, dict) for each in value)


def _number(cell: object) -> float | None:
    if isinstance(cell, bool) or not isinstance(cell, int | float):
        return None
    return None if math.isnan(cell) else float(cell)


def _number_or_text(cell: object) -> float | str:
    if isinstance(cell, int | float):
        return float(cell)
    try:
        return float(str(cell))
    except ValueError:
        return str(cell)


def _stamped_by(column: int) -> Callable[[Sequence[object]], datetime]:
    """A row's local time, from the pre-trial's column of dates and times."""

    def stamp(row: Sequence[object]) -> datetime:
        cell = row[column]
        if not isinstance(cell, datetime):
            raise ValueError(f"the pre-trial's climate is stamped by a date and time, not {cell!r}")
        return cell

    return stamp


def _key(cell: object) -> str:
    return re.sub(r"\s+", "", str(cell)).lower()


def _at(row: Sequence[object], index: int) -> object:
    return row[index] if index < len(row) else None


def _any(row: Iterable[object]) -> bool:
    return any(cell is not None for cell in row)


def _width(row: Sequence[object]) -> int:
    return sum(1 for cell in row if cell is not None)


def _pairs(times: Sequence[datetime]) -> Iterator[tuple[datetime, datetime]]:
    return itertools.pairwise(times)


if __name__ == "__main__":
    raise SystemExit(main())
