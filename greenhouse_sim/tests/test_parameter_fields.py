"""A crop model's parameters as their schema describes them (P20.1, decision
0077): each says what it is, its unit, its source and its range, each end
of the range with where it comes from, and a value outside the range is
refused by field. That each unit and source is its reproduction's is held
by the models' own tests (`test_tomgro.py`, `test_vanthoor.py`)."""

import json
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import BaseModel, ValidationError

from greenhouse_sim.biology.parameter_fields import TYPES_OWN
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters

MODELS: Final[tuple[type[BaseModel], ...]] = (TomgroParameters, VanthoorParameters)
# The keywords that bound a value from above.
MOST: Final = ("maximum", "exclusiveMaximum")
# Decision 0076's calibrations, each by its model's.
CALIBRATIONS: Final = (
    Path(__file__).resolve().parents[2] / "research" / "validation" / "agc4" / "calibrated"
)
CALIBRATED: Final[dict[str, type[BaseModel]]] = {
    "tomgro": TomgroParameters,
    "vanthoor_katzin": VanthoorParameters,
}


def _described(model: type[BaseModel]) -> dict[str, dict[str, Any]]:
    properties: dict[str, dict[str, Any]] = model.model_json_schema()["properties"]
    return properties


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_each_parameter_says_what_it_is_its_unit_its_source_and_its_range(
    model: type[BaseModel],
) -> None:
    described = _described(model)

    assert set(described) == set(model.model_fields)
    for name, field in described.items():
        assert field["description"], name
        assert field["unit"], name
        assert field["source"], name
        assert set(field["range_from"]) == {"least", "most"}, name


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_a_range_s_most_says_where_it_comes_from_unless_only_its_type_bounds_it(
    model: type[BaseModel],
) -> None:
    for name, field in _described(model).items():
        bounded = any(keyword in field for keyword in MOST)
        assert (field["range_from"]["most"] != TYPES_OWN) == bounded, name
        assert field["range_from"]["least"] == TYPES_OWN, name


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_the_published_set_is_within_its_ranges(model: type[BaseModel]) -> None:
    # A default is not validated where the model is made, so its values are
    # validated as a set's would be.
    published = model().model_dump()

    assert model.model_validate(published).model_dump() == published


@pytest.mark.parametrize(
    ("model", "name", "value"),
    [
        (TomgroParameters, "alpha_f", 1.01),
        (TomgroParameters, "df_max", 1.5),
        (TomgroParameters, "m", 1.0),
        (TomgroParameters, "trgh", 1.2),
        (TomgroParameters, "k", 0.0),
        (TomgroParameters, "delta", -0.01),
        (VanthoorParameters, "theta", 1.01),
        (VanthoorParameters, "eta_co2_air_stom", 1.1),
        (VanthoorParameters, "rho_can_par", 1.5),
        (VanthoorParameters, "rho_flr_par", 1.01),
        (VanthoorParameters, "sla", 0.0),
    ],
)
def test_a_value_outside_its_range_is_refused_by_its_field(
    model: type[BaseModel], name: str, value: float
) -> None:
    with pytest.raises(ValidationError) as refused:
        model.model_validate(model().model_dump() | {name: value})

    assert [error["loc"] for error in refused.value.errors()] == [(name,)]


@pytest.mark.parametrize(
    ("model", "name", "value"),
    [
        (TomgroParameters, "alpha_f", 1.0),
        (TomgroParameters, "m", 0.999),
        (VanthoorParameters, "theta", 1.0),
        (VanthoorParameters, "rho_flr_par", 1.0),
        # A field that only its type bounds takes any value of it.
        (TomgroParameters, "n_ff", -3.0),
        (VanthoorParameters, "c_fruit_max", 1e9),
    ],
)
def test_a_value_at_its_range_s_end_is_kept(
    model: type[BaseModel], name: str, value: float
) -> None:
    kept = model.model_validate(model().model_dump() | {name: value})

    assert getattr(kept, name) == value


@pytest.mark.parametrize(("name", "model"), CALIBRATED.items())
def test_decision_0076_s_calibrations_are_within_the_ranges(
    name: str, model: type[BaseModel]
) -> None:
    # A calibration's bounds are narrower than the ranges, and its values
    # within them, so that a range refuses neither.
    calibration = json.loads((CALIBRATIONS / f"{name}.json").read_text())
    published = model().model_dump()

    for parameter in calibration["parameters"]:
        for value in (*parameter["bounds"], parameter["calibrated"]):
            model.model_validate(published | {parameter["name"]: value})
