"""A crop model's parameter as the schema of its parameters describes it
(P20.1, decision 0077): what it is, its unit, where its value comes from,
and its range, the least and most value a parameter set may give it, each
end with where it comes from. A value outside the range is refused, by
field, when the parameter model is validated.

A range is wide: what the model's equations, or the quantity's meaning,
allow. A calibration's bounds are narrower, and stay in its own manifest
(decision 0076). An end that only the field's type bounds, such as not
negative, says so.
"""

from typing import Any, Final

from pydantic import BaseModel, Field, JsonValue

from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT

# The reason given for an end of a range that only the field's type bounds,
# if it does.
TYPES_OWN: Final = "none in its source: the field's type's"


def parameter(
    default: float,
    *,
    what: str,
    unit: str,
    source: str,
    most: float | None = None,
    below: float | None = None,
    most_from: str = TYPES_OWN,
) -> Any:
    """A parameter's field: its published `default`, what it is, its `unit`
    and its `source`. Its least is its type's; its most is `most`, or less
    than `below`, from `most_from`, or its type's."""
    return Field(
        default,
        description=what,
        le=most,
        lt=below,
        json_schema_extra={
            "unit": unit,
            "source": source,
            "range_from": {"least": TYPES_OWN, "most": most_from},
        },
    )


def parameters_json_schema(parameters: type[BaseModel]) -> dict[str, JsonValue]:
    """The schema a parameter model publishes: each field's default, what it
    is, its unit, its source, and its range with where each end comes
    from."""
    return {"$schema": JSON_SCHEMA_DIALECT, **parameters.model_json_schema()}
