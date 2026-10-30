"""Every JSON Schema the protocol publishes, from one list: the records a
run's gateway takes and writes, and what its routes answer (decision 0046),
and what a policy's port answers beside them (decision 0061), each committed file its
model's export in the 2020-12 dialect, written one way. They live in the
package (`greenhouse_protocol/schemas/`), for a consumer, a platform or an
executor in another language to check documents against.

After a model they describe changes, they are written again, from
`greenhouse_protocol/`:

    python tests/test_published_schemas.py --update
"""

import json
import sys
from pathlib import Path
from typing import Final

import pytest
from pydantic import BaseModel

from greenhouse_protocol.assignment import Assignment, ExecutionReport
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.consumer import ForecastBatch, OutcomeBatch
from greenhouse_protocol.contracts.gateway import GatewayLimits, PlanState, Receipt
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.plan import ActionKey, ActionState, Plan

SCHEMAS_DIR: Final = Path(__file__).resolve().parents[1] / "greenhouse_protocol" / "schemas"
JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"
# Each published schema's file, and the record it describes.
PUBLISHED: Final[dict[str, type[BaseModel]]] = {
    "plan.schema.json": Plan,
    "action-key.schema.json": ActionKey,
    "action-state.schema.json": ActionState,
    "action-outcome.schema.json": ActionOutcome,
    "assignment.schema.json": Assignment,
    "execution-report.schema.json": ExecutionReport,
    "authorisation-config.schema.json": AuthorisationConfig,
    "receipt.schema.json": Receipt,
    "plan-state.schema.json": PlanState,
    "gateway-limits.schema.json": GatewayLimits,
    "outcome-batch.schema.json": OutcomeBatch,
    "capability-context.schema.json": CapabilityContext,
    "information-budget.schema.json": InformationBudget,
    "forecast.schema.json": Forecast,
    "forecast-batch.schema.json": ForecastBatch,
}


def _without_discriminators(value: object) -> object:
    """A schema without OpenAPI's `discriminator` keyword, with which Pydantic
    marks a tagged union: it is not JSON Schema, and the `oneOf` and each
    case's constant tag already say the same."""
    if isinstance(value, dict):
        return {
            key: _without_discriminators(item)
            for key, item in value.items()
            if not (key == "discriminator" and isinstance(item, dict) and "propertyName" in item)
        }
    if isinstance(value, list):
        return [_without_discriminators(item) for item in value]
    return value


def _schema_text(model: type[BaseModel]) -> str:
    schema = {"$schema": JSON_SCHEMA_DIALECT, **model.model_json_schema()}
    return json.dumps(_without_discriminators(schema), indent=2, ensure_ascii=False) + "\n"


@pytest.mark.parametrize("file_name", sorted(PUBLISHED))
def test_each_published_schema_is_its_records_export(file_name: str) -> None:
    published = SCHEMAS_DIR / file_name

    assert published.exists(), f"{file_name} is not written: python {__file__} --update"
    assert published.read_text() == _schema_text(PUBLISHED[file_name]), (
        f"{file_name} is not its record's export: python {__file__} --update"
    )


def test_the_schemas_say_what_a_record_refuses_across_its_fields() -> None:
    """What JSON Schema can say of the checks across a record's fields, the
    published schemas say too; what it cannot (a plan's graph, an outcome's
    agreement with its status) the records and the conformance checks do."""
    defs = json.loads((SCHEMAS_DIR / "plan.schema.json").read_text())["$defs"]

    assert [sorted(case["required"]) for case in defs["Lower"]["oneOf"]] == [
        ["by_cm"],
        ["by_internodes"],
        ["to_head_room_m"],
    ]
    assert defs["Harvest"]["if"] == {"properties": {"scope": {"const": "ripe"}}}
    assert defs["Harvest"]["else"]["required"] == ["organ_id"]
    assert defs["Lateness"]["then"]["required"] == ["fallback"]
    assert [case["required"] for case in defs["Recurrence"]["oneOf"]] == [["count"], ["until"]]


def test_no_schema_is_published_outside_the_list() -> None:
    assert {path.name for path in SCHEMAS_DIR.glob("*.schema.json")} == set(PUBLISHED)


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        sys.exit(f"usage: python {sys.argv[0]} --update")
    SCHEMAS_DIR.mkdir(exist_ok=True)
    for name, model in PUBLISHED.items():
        (SCHEMAS_DIR / name).write_text(_schema_text(model))
        print(f"wrote {SCHEMAS_DIR / name}")
