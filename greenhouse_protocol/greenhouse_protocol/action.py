"""The semantic action contract: what someone wants done to a greenhouse.

An action request is a contract, not a decision. The same request should
be expressible whether its executor is the simulator, a human workflow, a
greenhouse controller or a robot, and the party that decides what should
happen is not the party that carries it out. So these types belong to no
decision-maker and no executor: a policy proposes them, an executor
validates and performs them against its own view of the world, and the
outcome comes back as an `ActionOutcome` (`greenhouse_protocol.execution`).

Deprecated (decision 0046): one action format replaces these requests,
`greenhouse_protocol.actions`, carried in a plan (`greenhouse_protocol.plan`)
and ending in an outcome (`greenhouse_protocol.outcome`). They stay, as they
are, until the simulator carries the new format out, and go then (P13).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# The hard upper bound on a single watering request: the one format's.
from greenhouse_protocol.actions import MAX_WATER_AMOUNT_ML as MAX_WATER_AMOUNT_ML


class WaterPlantAction(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    action_type: Literal["WATER_PLANT"] = "WATER_PLANT"
    plant_id: str
    amount_ml: float


class HarvestPlantAction(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    action_type: Literal["HARVEST_PLANT"] = "HARVEST_PLANT"
    plant_id: str


class LowerPlantAction(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    action_type: Literal["LOWER_PLANT"] = "LOWER_PLANT"
    plant_id: str
    amount_cm: float


class ScheduleInspectionAction(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    action_type: Literal["SCHEDULE_INSPECTION"] = "SCHEDULE_INSPECTION"
    plant_id: str
    reason: str


RequestedAction = (
    WaterPlantAction | HarvestPlantAction | LowerPlantAction | ScheduleInspectionAction
)


class ActionResult(BaseModel):
    """The outcome of checking a request, before anything is executed."""

    model_config = ConfigDict(validate_assignment=True)

    accepted: bool
    reason: str | None = None
