"""The first action format, removed in P13.9, does not come back: one
format acts on a greenhouse, an `Action` in a `Plan`, ending in an outcome
(decision 0046)."""

import importlib
import pkgutil
from typing import Final

import pytest

import greenhouse_protocol

# Its requests, the check of one, and its outcome.
REMOVED_MODULES: Final = ("greenhouse_protocol.action", "greenhouse_protocol.execution")
# Its names, in the modules above and beside them: `ActionExecutionAdapter`
# in `contracts.execution`, and `ActionExecutorType` in `enums`.
REMOVED_NAMES: Final = frozenset(
    {
        "RequestedAction",
        "WaterPlantAction",
        "HarvestPlantAction",
        "LowerPlantAction",
        "ScheduleInspectionAction",
        "ActionResult",
        "ExecutionStatus",
        "ActionExecutionAdapter",
        "ActionExecutorType",
    }
)


@pytest.mark.parametrize("module", REMOVED_MODULES)
def test_a_removed_module_does_not_come_back(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_no_module_of_the_protocol_has_a_removed_name() -> None:
    kept = {
        module.name: sorted(REMOVED_NAMES & set(dir(importlib.import_module(module.name))))
        for module in pkgutil.walk_packages(
            greenhouse_protocol.__path__, f"{greenhouse_protocol.__name__}."
        )
    }

    assert {name: names for name, names in kept.items() if names} == {}
