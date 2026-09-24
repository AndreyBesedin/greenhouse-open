from datetime import UTC, datetime
from io import BytesIO

import openpyxl
import pytest
from greenhouse_protocol.enums import ObservationType

from greenhouse_adapters.wur.agc4_pretrial_2023.compartments import COMPARTMENT_ID, GREENHOUSE_ID
from greenhouse_adapters.wur.agc4_pretrial_2023.crops import (
    CropMeasurements,
    read_crop_measurements,
)

IDENTITY = ["Date", "Week", "# on label", "Treatment", "Variety", "Corrected EC", "Light"]
SINGLE = ["field", "Plant repetition#", "Plantheigth", "# leaves", "leaf length", "leaf width"]


def _truss_headers() -> list[str]:
    """The real sheet's truss columns, including truss 3's unnumbered red."""
    headers = []
    for truss in range(1, 6):
        for kind in ("flowering", "set", "yellow", "orange", "red"):
            name = f"# {kind} trus{truss}"
            headers.append("#  red trus" if (kind, truss) == ("red", 3) else name)
    return headers


HEADER = IDENTITY + SINGLE + _truss_headers() + ["#trusses", "note", "Sum of flowers"]


def _row(label: int, week: int, day: datetime, **values: object) -> list[object]:
    cells: dict[str, object] = dict.fromkeys(HEADER)
    cells.update(
        {
            "Date": day,
            "Week": week,
            "# on label": label,
            "Treatment": "Cherry_EC6_HighLight",
            "Variety": "Cherry",
            "Corrected EC": "EC6",
            "Light": "high light",
            "field": 9,
            "Plant repetition#": 1 if label == 41 else 2,
        }
    )
    cells.update(values)
    return [cells[name] for name in HEADER]


def _read(*rows: list[object]) -> CropMeasurements:
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "All data"
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    book.save(buffer)
    buffer.seek(0)
    return read_crop_measurements(buffer)


ROWS = (
    _row(
        41,
        42,
        datetime(2023, 10, 18),
        Plantheigth=30,
        **{
            "# flowering trus1": 2,
            "# flowering trus2": 1,
            "# set trus1": 5,
            "#trusses": 4,
            # the sheet's own sum, which must not be trusted
            "Sum of flowers": 3,
        },
    ),
    _row(
        41,
        44,
        datetime(2023, 11, 1),
        Plantheigth=33,
        **{
            "# set trus1": 0,
            "# set trus2": 2,
            "# yellow trus1": 1,
            "# orange trus2": 1,
            "# red trus1": 2,
            "#  red trus": 1,  # truss 3's unnumbered red column
            "#trusses": 5,
            "Sum of flowers": 0,  # no flowering cell measured
        },
    ),
    _row(47, 39, datetime(2023, 9, 27), Plantheigth=20),
    _row(47, 40, datetime(2023, 10, 4), Plantheigth=25),
)


def _values(
    measurements: CropMeasurements, plant_id: str, at: datetime
) -> dict[ObservationType, float]:
    return {
        o.observation_type: o.value
        for o in measurements.observations
        if o.plant_id == plant_id and o.timestamp == at
    }


def test_plants_come_from_labels_with_field_repetition_and_treatment() -> None:
    measurements = _read(*ROWS)

    assert [p.plant_id for p in measurements.plants] == ["wur23_p41", "wur23_p47", "wur23_p47b"]
    first = measurements.plants[0]
    assert (first.variety, first.row, first.position_in_row, first.zone) == (
        "cherry",
        9,
        1,
        "high light / EC6",
    )


def test_counts_are_summed_from_measured_cells_only() -> None:
    measurements = _read(*ROWS)

    # 18 October is summer time: local noon is 10:00Z
    october = _values(measurements, "wur23_p41", datetime(2023, 10, 18, 10, tzinfo=UTC))
    assert october == {
        ObservationType.PLANT_HEIGHT_CM: 30.0,
        ObservationType.OPEN_FLOWER_COUNT: 3.0,
        ObservationType.GREEN_FRUIT_COUNT: 5.0,
        ObservationType.TRUSS_COUNT: 4.0,
    }
    # 1 November is winter time: local noon is 11:00Z. No flowering cell was
    # measured, so there is no flower count, whatever the sheet's sum says.
    november = _values(measurements, "wur23_p41", datetime(2023, 11, 1, 11, tzinfo=UTC))
    assert november == {
        ObservationType.PLANT_HEIGHT_CM: 33.0,
        ObservationType.GREEN_FRUIT_COUNT: 2.0,
        ObservationType.RIPE_FRUIT_COUNT: 3.0,
        ObservationType.COLOURED_FRUIT_COUNT: 5.0,
        ObservationType.TRUSS_COUNT: 5.0,
    }


def test_label_47_is_a_different_plant_from_week_40() -> None:
    measurements = _read(*ROWS)

    heights = {
        o.plant_id: o.value
        for o in measurements.observations
        if o.observation_type == ObservationType.PLANT_HEIGHT_CM and o.plant_id != "wur23_p41"
    }
    assert heights == {"wur23_p47": 20.0, "wur23_p47b": 25.0}


def test_observations_belong_to_the_pretrial_compartment() -> None:
    measurements = _read(*ROWS)

    assert all(o.greenhouse_id == GREENHOUSE_ID for o in measurements.observations)
    assert all(o.compartment_id == COMPARTMENT_ID for o in measurements.observations)
    assert len({o.observation_id for o in measurements.observations}) == len(
        measurements.observations
    )


def test_a_plant_whose_treatment_changes_between_weeks_is_refused() -> None:
    moved = _row(41, 43, datetime(2023, 10, 25), Light="low light")

    with pytest.raises(ValueError, match="changes treatment"):
        _read(ROWS[0], moved)
