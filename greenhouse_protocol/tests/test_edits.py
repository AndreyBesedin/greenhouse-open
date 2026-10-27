"""Every model in the protocol either cannot be edited or checks its edits,
so that no record holds a value its type refuses."""

import importlib
import inspect
import pkgutil

from pydantic import BaseModel

import greenhouse_protocol


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

    assert {"Observation", "GreenhouseDescription", "Plant", "Plan"} <= {
        model.__name__ for model in models
    }
    assert unchecked == []
