"""Admissibility checks for an action about to be executed in simulation.

Request, validation, execution and observed outcome are distinct, and
validation belongs at the boundary where the action is actually executed,
against whatever that executor can see. This executor is the simulator, and
what it can see is the simulated world. A human-workflow or device executor
validates differently, against what it can see - the shared part is the
request and the result, which live in `greenhouse_protocol.action`.
"""

from greenhouse_protocol.action import MAX_WATER_AMOUNT_ML as MAX_WATER_AMOUNT_ML
from greenhouse_protocol.action import (
    ActionResult,
    LowerPlantAction,
    RequestedAction,
    ScheduleInspectionAction,
    WaterPlantAction,
)

from greenhouse_sim.world import GreenhouseWorld


def validate_action(world: GreenhouseWorld, action: RequestedAction) -> ActionResult:
    """Checks a requested action against the simulated world before execution.

    A hard-constraint check, independent of which policy proposed the
    action. Never trusts that an action is valid because a human approved it
    or an agent proposed it.
    """
    try:
        plant = world.plant(action.plant_id)
    except LookupError:
        return ActionResult(accepted=False, reason=f"plant {action.plant_id!r} does not exist")

    if isinstance(action, WaterPlantAction):
        if not (0 < action.amount_ml <= MAX_WATER_AMOUNT_ML):
            return ActionResult(accepted=False, reason="water amount out of range")
    elif isinstance(action, LowerPlantAction):
        visible_height = plant.stem_length_cm - plant.lowered_length_cm
        if not (0 < action.amount_cm <= visible_height):
            return ActionResult(accepted=False, reason="lowering amount exceeds visible height")
    elif isinstance(action, ScheduleInspectionAction):
        if not action.reason.strip():
            return ActionResult(accepted=False, reason="inspection reason is required")

    return ActionResult(accepted=True)
