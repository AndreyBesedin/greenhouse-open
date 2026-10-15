"""Every model in the protocol either cannot be edited or checks its edits,
so that no record holds a value its type refuses."""

import importlib
import inspect
import pkgutil

import pytest
from pydantic import BaseModel, ValidationError

import greenhouse_protocol
from greenhouse_protocol.action import WaterPlantAction
from greenhouse_protocol.execution import ActionOutcome, ExecutionStatus


def _protocol_models() -> set[type[BaseModel]]:
    models: set[type[BaseModel]] = set()
    for module_info in pkgutil.walk_packages(
        greenhouse_protocol.__path__, f"{greenhouse_protocol.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        models.update(
            model
            for _, model in inspect.getmembers(module, inspect.isclass)
            if issubclass(model, BaseModel) and model.__module__ == module.__name__
        )
    return models


def test_every_protocol_model_is_frozen_or_checks_its_edits() -> None:
    models = _protocol_models()
    unchecked = sorted(
        model.__name__
        for model in models
        if not (model.model_config.get("frozen") or model.model_config.get("validate_assignment"))
    )

    assert {"Observation", "GreenhouseDescription", "Plant", "WaterPlantAction"} <= {
        model.__name__ for model in models
    }
    assert unchecked == []


def test_an_action_refuses_an_edit_its_type_refuses() -> None:
    action = WaterPlantAction(plant_id="p1", amount_ml=100.0)

    with pytest.raises(ValidationError):
        action.amount_ml = "a lot"  # type: ignore[assignment]
    with pytest.raises(ValidationError):
        action.action_type = "HARVEST_PLANT"  # type: ignore[assignment]
    assert action == WaterPlantAction(plant_id="p1", amount_ml=100.0)

    action.amount_ml = 250.0
    assert action.amount_ml == 250.0


def test_an_outcome_refuses_a_status_that_does_not_exist_and_takes_a_reason() -> None:
    outcome = ActionOutcome(status=ExecutionStatus.REJECTED, reason="no such plant")

    with pytest.raises(ValidationError):
        outcome.status = "PENDING"  # type: ignore[assignment]
    assert outcome.status == ExecutionStatus.REJECTED

    outcome.reason = "plant harvested"
    assert outcome.reason == "plant harvested"
