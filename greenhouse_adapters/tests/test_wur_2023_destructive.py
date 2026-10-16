from datetime import UTC, datetime
from io import BytesIO

import openpyxl
import pytest
from greenhouse_protocol.enums import EventType

from greenhouse_adapters.wur.agc4_pretrial_2023.compartments import COMPARTMENT_ID
from greenhouse_adapters.wur.agc4_pretrial_2023.destructive import (
    SHEET,
    parameter_name,
    read_destructive_samples,
)

HEADER = (
    "Date",
    "Phase",
    "DAS",
    "Treatment",
    "Variety",
    "EC",
    "Light",
    "Plant density (p/m2)",
    "Sample n",
    "Sample name",
    "FW leaves (g/plant)",
    "Trusses (#/plant)",
)
SEP_4 = datetime(2023, 9, 4)
SEP_18 = datetime(2023, 9, 18)


def _row(
    day: datetime, treatment: str, ec: str, light: str, leaves_g: object, trusses: int
) -> tuple[object, ...]:
    """A cherry sample, the first of its treatment, 25 plants per square
    metre: on 4 September in the transplant phase, 28 days after sowing,
    on 18 September in the generative one, 42 days after."""
    phase, das = ("Transplant", 28) if day == SEP_4 else ("Generative", 42)
    name = f"Cherry_{ec}_{light}_1"
    return (day, phase, das, treatment, "Cherry", ec, light, 25, 1, name, leaves_g, trusses)


# Two copies of one untreated plant, listed under two treatments' names, then
# two treated samples, one of them with a measurement not made.
ROWS = (
    _row(SEP_4, "No treatment", "EC3", "ML", 12.5, 0),
    _row(SEP_4, "No treatment", "EC5", "HL", 12.5, 0),
    _row(SEP_18, "EC3 ML", "EC3", "ML", 80.0, 2),
    _row(SEP_18, "EC5 HL", "EC5", "HL", "N/A", 3),
)


def _workbook(*rows: tuple[object, ...], header: tuple[str, ...] = HEADER) -> BytesIO:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = SHEET
    sheet.append(("Destructive harvests, 4th Autonomous Greenhouse Challenge pre-trial",))
    sheet.append(header)
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def test_an_untreated_plant_listed_under_several_treatments_is_one_sample() -> None:
    untreated = [e for e in read_destructive_samples(_workbook(*ROWS)) if e.timestamp.day == 4]

    assert len(untreated) == 1
    assert untreated[0].event_id == "wur23_sample_20230904_untreated_1"
    assert untreated[0].parameters["listed_as"] == ["Cherry_EC3_ML_1", "Cherry_EC5_HL_1"]
    assert "ec" not in untreated[0].parameters and "light" not in untreated[0].parameters


def test_each_treated_sample_is_a_compartment_event_at_local_noon_with_what_was_measured() -> None:
    treated = [e for e in read_destructive_samples(_workbook(*ROWS)) if e.timestamp.day == 18]

    assert [e.event_id for e in treated] == [
        "wur23_sample_20230918_Cherry_EC3_ML_1",
        "wur23_sample_20230918_Cherry_EC5_HL_1",
    ]
    first, second = treated
    assert first.event_type == EventType.DESTRUCTIVE_SAMPLE
    assert first.compartment_id == COMPARTMENT_ID and first.plant_id is None
    # 12:00 in Amsterdam's summer time
    assert first.timestamp == datetime(2023, 9, 18, 10, tzinfo=UTC)
    assert first.parameters["phase"] == "Generative"
    assert first.parameters["days_after_sowing"] == 42
    assert first.parameters["fw_leaves_g_per_plant"] == 80.0
    assert first.parameters["trusses_count_per_plant"] == 2
    # N/A is a measurement not made, left out rather than recorded as a value
    assert "fw_leaves_g_per_plant" not in second.parameters


def test_a_sample_name_repeated_on_one_date_is_refused() -> None:
    with pytest.raises(ValueError, match="repeat on the same date"):
        read_destructive_samples(_workbook(ROWS[2], ROWS[2]))


def test_a_sheet_missing_a_column_or_its_header_is_refused() -> None:
    with pytest.raises(ValueError, match="missing columns \\['DAS'\\]"):
        read_destructive_samples(_workbook(header=tuple(c for c in HEADER if c != "DAS")))
    with pytest.raises(ValueError, match="no header row"):
        read_destructive_samples(_workbook(header=("Date", "Phase")))


@pytest.mark.parametrize(
    ("header", "name"),
    [
        ("FW leaves (g/plant)", "fw_leaves_g_per_plant"),
        ("Trusses (#/plant)", "trusses_count_per_plant"),
        ("Leaf area (cm²/plant)", "leaf_area_cm2_per_plant"),
        ("SLA (cm2/g)", "sla_cm2_per_g"),
    ],
)
def test_a_measurement_is_named_by_its_header_with_its_unit(header: str, name: str) -> None:
    assert parameter_name(header) == name
