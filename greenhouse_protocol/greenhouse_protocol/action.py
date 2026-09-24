"""The semantic action contract: what someone wants done to a greenhouse.

An action request is a contract, not a decision. The same request should
be expressible whether its executor is the simulator, a human workflow, a
greenhouse controller or a robot, and the party that decides what should
happen is not the party that carries it out. So these types belong to no
decision-maker and no executor: a policy proposes them, an executor
validates and performs them against its own view of the world, and the
outcome comes back as an `ActionOutcome` (`greenhouse_protocol.execution`).
"""

from typing import Literal

from pydantic import BaseModel

# The hard upper bound on a single watering request. Part of the contract
# rather than of any one executor: whatever proposes an action can know it
# in advance, and every executor's validation enforces it.
MAX_WATER_AMOUNT_ML = 2000.0


class WaterPlantAction(BaseModel):
    action_type: Literal["WATER_PLANT"] = "WATER_PLANT"
    plant_id: str
    amount_ml: float


class HarvestPlantAction(BaseModel):
    action_type: Literal["HARVEST_PLANT"] = "HARVEST_PLANT"
    plant_id: str


class LowerPlantAction(BaseModel):
    action_type: Literal["LOWER_PLANT"] = "LOWER_PLANT"
    plant_id: str
    amount_cm: float


class ScheduleInspectionAction(BaseModel):
    action_type: Literal["SCHEDULE_INSPECTION"] = "SCHEDULE_INSPECTION"
    plant_id: str
    reason: str


RequestedAction = (
    WaterPlantAction | HarvestPlantAction | LowerPlantAction | ScheduleInspectionAction
)


class ActionResult(BaseModel):
    """The outcome of checking a request, before anything is executed."""

    accepted: bool
    reason: str | None = None
