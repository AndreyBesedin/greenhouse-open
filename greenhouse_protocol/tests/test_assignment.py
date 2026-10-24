"""What passes between a gateway and an executor (decision 0046): an
assignment, and the executor's report of it."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from greenhouse_protocol.actions import ActionRef, Lower
from greenhouse_protocol.assignment import Assignment, ExecutionReport, ReportStatus
from greenhouse_protocol.outcome import Lowered

TEN = datetime(2026, 3, 1, 10, tzinfo=UTC)
MINUTE = timedelta(minutes=1)


def test_an_assignment_starts_at_an_instant_and_by_its_deadline() -> None:
    assignment = Assignment(
        assignment_id="a1",
        run_id="run_1",
        ref=ActionRef(action_id="lower", occurrence=2),
        action=Lower(plant_id="p30", by_internodes=1),
        at=TEN,
        deadline=TEN + MINUTE,
    )

    assert Assignment.model_validate_json(assignment.model_dump_json()) == assignment
    with pytest.raises(ValidationError, match="no earlier than its start"):
        assignment.model_validate({**assignment.model_dump(), "deadline": TEN - MINUTE})


def test_an_assignment_carries_no_principal() -> None:
    assert "principal" not in Assignment.model_fields
    assert "proposed_by" not in Assignment.model_fields


def test_a_report_of_each_status() -> None:
    reports = [
        ExecutionReport(
            assignment_id="a1",
            status=ReportStatus.DONE,
            started_at=TEN,
            finished_at=TEN + MINUTE,
            effect=Lowered(by_cm=25),
            event_id="sim_p01_lowering",
        ),
        ExecutionReport(
            assignment_id="a1", status=ReportStatus.FAILED, started_at=TEN, reason="stuck"
        ),
        ExecutionReport(assignment_id="a1", status=ReportStatus.REFUSED, reason="leaves remain"),
    ]

    for report in reports:
        assert ExecutionReport.model_validate_json(report.model_dump_json()) == report


@pytest.mark.parametrize(
    "fields, reason",
    [
        (dict(status=ReportStatus.DONE, started_at=TEN), "start and its finish"),
        (dict(status=ReportStatus.FAILED), "says why"),
        (dict(status=ReportStatus.FAILED, reason="stuck"), "was attempted"),
        (dict(status=ReportStatus.REFUSED, reason="no", finished_at=TEN), "that finished started"),
        (dict(status=ReportStatus.REFUSED, reason="no", started_at=TEN), "never started"),
        (dict(status=ReportStatus.REFUSED, reason="no", event_id="e1"), "made no event"),
        (
            dict(status=ReportStatus.FAILED, reason="no", started_at=TEN, effect=Lowered(by_cm=1)),
            "no effect",
        ),
        (
            dict(status=ReportStatus.DONE, started_at=TEN, finished_at=TEN - MINUTE),
            "finishes no earlier",
        ),
    ],
)
def test_a_report_agrees_with_its_status(fields: dict[str, object], reason: str) -> None:
    with pytest.raises(ValidationError, match=reason):
        ExecutionReport.model_validate({"assignment_id": "a1", **fields})
