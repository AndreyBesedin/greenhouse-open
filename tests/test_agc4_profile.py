"""The AGC4 profile counts what the archives hold (research priorities, item
5), on miniature archives shaped as the real ones are: no data needed."""

import io
import zipfile
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

from research.validation.agc4 import profile

TIMESERIES = "autonomous_greenhouse_challenge4_timeseries"


def _workbook(sheets: dict[str, list[list[object]]]) -> bytes:
    book = openpyxl.Workbook()
    for sheet in book.worksheets:
        book.remove(sheet)
    for title, rows in sheets.items():
        sheet = book.create_sheet(title)
        for row in rows:
            sheet.append(row)
    written = io.BytesIO()
    book.save(written)
    return written.getvalue()


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


FINAL_HEADER: list[object] = [
    "GH #",
    "plant",
    "FW tot",
    "# tot",
    "# tom green",
    "fw green",
    "#tom red",
    "FW red",
]


def _challenge(tmp_path: Path) -> Path:
    csv = (
        "time,compartment/air_temperature,dwarf_tomato/plant_density,weather/wind_direction\n"
        "2024-10-27 02:50:00+02:00,18.5,56.0,4.0\n"
        "2024-10-27 02:55:00+02:00,,,4.0\n"
        "2024-10-27 02:00:00+01:00,18.7,,8.0\n"
        "2024-10-27 02:05:00+01:00,18.6,,2.0\n"
    )
    harvest = _workbook(
        {
            "Information": [["Legend", "Description", "unit"]],
            "Destructive harvest 7-10-24": [
                ["plant", "FW ", "# tom"],
                ["306-1", 80.0, 30],
                ["306-2", 70.0, 31],
                [306, 75.0, 30.5],
            ],
            "Final Harvest  3.06": [
                FINAL_HEADER,
                [306, "306-1", 300.0, 40, 10, 60.0, 30, 240.0],
                [306, "306-2", 250.0, 35, 5, 30.0, 30, 220.0],
                [306, "306-3", None, 33, None, None, 33, 260.0],
                ["total", None, None, None, None, None, None, 720.0],
                ["drying", None, None, None, None, 100.0, 10, 200.0],
                [None, None, None, None, None, 8.0, None, 14.0],
                [None, None, None, None, None, 8.0, None, 7.0],
            ],
        }
    )
    return _zip(
        tmp_path / "challenge.zip",
        {
            f"{TIMESERIES}/timeseries/reference.csv": csv.encode(),
            f"{TIMESERIES}/Harvest.xlsx": harvest,
            f"{TIMESERIES}/.DS_Store": b"",
            f"__MACOSX/{TIMESERIES}/timeseries/._reference.csv": b"",
        },
    )


def test_a_csv_says_its_rows_span_step_and_how_full_each_column_is(tmp_path: Path) -> None:
    table = profile.profile_challenge(_challenge(tmp_path))["time_series"]

    assert list(table) == ["reference.csv"]
    reference = table["reference.csv"]
    # The clock change's repeated hour is told apart by its offset: steps of 5 minutes.
    assert reference["rows"] == 4
    assert reference["first"] == "2024-10-27T02:50:00+02:00"
    assert reference["last"] == "2024-10-27T02:05:00+01:00"
    assert reference["step_s"] == 300
    columns = reference["columns"]
    assert columns["compartment/air_temperature"]["present"] == 3
    assert columns["compartment/air_temperature"]["missing_share"] == 0.25
    assert columns["dwarf_tomato/plant_density"] == {
        "present": 1,
        "missing_share": 0.75,
        "values": [56.0],
    }
    assert columns["weather/wind_direction"]["values"] == [2.0, 4.0, 8.0]


def test_a_harvest_sheet_counts_its_plants_and_the_fruit_dried(tmp_path: Path) -> None:
    sheets = profile.profile_challenge(_challenge(tmp_path))["harvest"]["sheets"]

    assert sheets["Information"]["plants"] == {}
    sampling = sheets["Destructive harvest 7-10-24"]
    assert sampling["header"] == ["plant", "FW", "# tom"]
    # The compartment's mean row is not a plant.
    assert sampling["plants"] == {"3.06": 2}
    final = sheets["Final Harvest  3.06"]
    assert final["plants"] == {"3.06": 3}
    assert final["sorted_by_colour"] == 2
    assert final["red_alone"] == 1
    # Over the three plants, and over the two sorted by colour.
    assert final["red_fresh_g_per_plant"] == {"every_plant": 240.0, "sorted_by_colour": 230.0}
    assert final["dried"] == [
        {
            "fruit": "green",
            "fruits": None,
            "fresh_g": 100.0,
            "dry_g": 8.0,
            "dry_matter_percent": 8.0,
            "sheet_percent": 8.0,
        },
        {
            "fruit": "red",
            "fruits": 10.0,
            "fresh_g": 200.0,
            "dry_g": 14.0,
            "dry_matter_percent": 7.0,
            "sheet_percent": 7.0,
        },
    ]


def test_the_pretrial_climate_is_a_table_and_nan_is_missing(tmp_path: Path) -> None:
    climate = _workbook(
        {
            "weather_climate": [
                ["datenum", "date", "time", "tout", "part1"],
                [739134.0, datetime(2023, 9, 5, 0, 0), datetime(2023, 9, 5, 0, 0), "NaN", "NaN"],
                [739134.1, datetime(2023, 9, 5, 0, 5), datetime(2023, 9, 5, 0, 5), 17.4, 0],
            ],
            "Info": [["Variable", "Description", "Unit"], ["tout", "Outside", "°C"]],
        }
    )
    crop = _workbook({"All data": [["a", "b", "c"], [1, 2, None]]})
    archive = _zip(
        tmp_path / "pretrial.zip",
        {"ClimateTimeseries.xlsx": climate, "CropMeasurements.xlsx": crop},
    )

    workbooks = profile.profile_pretrial(archive)["workbooks"]

    assert workbooks["CropMeasurements.xlsx"] == {"sheets": {"All data": {"rows": 2, "columns": 3}}}
    table = workbooks["ClimateTimeseries.xlsx"]["climate"]
    assert table["rows"] == 2
    assert table["first"] == "2023-09-05T00:00:00"
    assert table["step_s"] == 300
    # The stamps are not channels.
    assert list(table["columns"]) == ["tout", "part1"]
    assert table["columns"]["tout"] == {"present": 1, "missing_share": 0.5, "values": [17.4]}


def test_it_refuses_an_archive_not_downloaded(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="greenhouse-data prepare"):
        profile.main(["--data-dir", str(tmp_path)])


def test_it_writes_an_object_of_plain_values_on_one_line() -> None:
    text = profile.written(
        {
            "reference.csv": {"rows": 2, "columns": {"a": {"present": 1, "values": [1.0]}}},
            "dried": [{"fruit": "red"}],
        }
    )

    assert text.splitlines() == [
        "{",
        ' "reference.csv": {',
        '  "rows": 2,',
        '  "columns": {',
        '   "a": {"present": 1, "values": [1.0]}',
        "  }",
        " },",
        ' "dried": [{"fruit": "red"}]',
        "}",
    ]
