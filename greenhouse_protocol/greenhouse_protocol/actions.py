"""What is to be done to a greenhouse, to what: one action format
(decision 0046).

An action is a kind, the things it acts on by identifier, and its
parameters; it names no time, no executor and no principal, which belong
to the planned action that carries it (`greenhouse_protocol.plan`). Every
kind is one member of `Action`, a union by `kind`, and a new kind is a new
member: no other type of action is proposed, planned or reported. A
model's own operations inside a simulator are not actions.

This replaces `greenhouse_protocol.action`, whose requests stay, deprecated,
until the simulator carries this format out (P13).
"""

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# The hard upper bound on a single watering. Part of the contract rather
# than of any one executor: whatever proposes an action can know it in
# advance, and every executor's checks enforce it.
MAX_WATER_AMOUNT_ML: Final = 2000.0
# A heating setpoint lies in this range, in °C, wherever it is set.
HEATING_SETPOINT_RANGE_C: Final = (0.0, 40.0)

# The protocol's own identifier, for actions and plans: letters, digits,
# '_', '.' and '-'. An occurrence or a fallback is named by `ActionRef`,
# not by a longer string.
type Identifier = Annotated[str, StringConstraints(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")]
type ActionId = Identifier
# What an action acts on: a device, a plant, an organ, by the greenhouse's
# own identifier for it.
type ItemName = Annotated[str, StringConstraints(min_length=1)]


class ActionKind(StrEnum):
    SET_LEVEL = "set_level"
    SET_TARGET = "set_target"
    WATER = "water"
    HARVEST = "harvest"
    LOWER = "lower"
    REMOVE_LEAF = "remove_leaf"
    INSPECT = "inspect"


class SetLevel(BaseModel):
    """A device's level, from 0 (off) to 1 (full), or `auto` to hand the
    device back to whatever control loop runs it. A door or vent is a
    device, its level how far it is open."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal[ActionKind.SET_LEVEL] = ActionKind.SET_LEVEL
    device_id: ItemName
    level: Annotated[float, Field(ge=0.0, le=1.0)] | Literal["auto"]


class SetTarget(BaseModel):
    """A climate controller's heating setpoint, by day or by night, in °C.
    Each kind of target has its own unit and range: the venting and humidity
    targets, when a controller has them, are members of their own beside
    this one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal[ActionKind.SET_TARGET] = ActionKind.SET_TARGET
    target: Literal["heating_day", "heating_night"]
    value_c: Annotated[float, Field(ge=HEATING_SETPOINT_RANGE_C[0], le=HEATING_SETPOINT_RANGE_C[1])]


class Water(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal[ActionKind.WATER] = ActionKind.WATER
    plant_id: ItemName
    amount_ml: Annotated[float, Field(gt=0.0, le=MAX_WATER_AMOUNT_ML)]


class HarvestScope(StrEnum):
    RIPE = "ripe"  # every ripe fruit the plant bears
    FRUIT = "fruit"  # one fruit, by its organ's identifier
    TRUSS = "truss"  # one truss, by its organ's identifier


class Harvest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal[ActionKind.HARVEST] = ActionKind.HARVEST
    plant_id: ItemName
    scope: HarvestScope
    # The fruit or the truss, for those scopes; none for every ripe fruit.
    organ_id: ItemName | None = None

    @model_validator(mode="after")
    def _organ_with_its_scope(self) -> Self:
        if (self.scope == HarvestScope.RIPE) != (self.organ_id is None):
            raise ValueError(
                "a harvest names its organ for a fruit or a truss, and none for every ripe fruit"
            )
        return self


class Lower(BaseModel):
    """Lower a plant's stem: by so many centimetres, by so many internodes,
    or until its top has so much head room under its wire. Exactly one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal[ActionKind.LOWER] = ActionKind.LOWER
    plant_id: ItemName
    by_cm: Annotated[float, Field(gt=0.0)] | None = None
    by_internodes: Annotated[int, Field(gt=0)] | None = None
    to_head_room_m: Annotated[float, Field(ge=0.0)] | None = None

    @model_validator(mode="after")
    def _one_measure(self) -> Self:
        given = [self.by_cm, self.by_internodes, self.to_head_room_m]
        if sum(measure is not None for measure in given) != 1:
            raise ValueError(
                "a lowering gives exactly one of by_cm, by_internodes and to_head_room_m"
            )
        return self


class RemoveLeaf(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal[ActionKind.REMOVE_LEAF] = ActionKind.REMOVE_LEAF
    plant_id: ItemName
    leaf_id: ItemName


class Inspect(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal[ActionKind.INSPECT] = ActionKind.INSPECT
    plant_id: ItemName
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


type Action = Annotated[
    SetLevel | SetTarget | Water | Harvest | Lower | RemoveLeaf | Inspect,
    Field(discriminator="kind"),
]


class ActionRef(BaseModel):
    """Which action a record is about: a planned action, one occurrence of a
    recurring one, or the fallback carried out in its place. `str()` spells
    it for people, `harvest@3` or `vent/fallback`; records keep the parts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: ActionId
    # Which occurrence of a recurring action, from 0; None for a one-off.
    occurrence: Annotated[int, Field(ge=0)] | None = None
    fallback: bool = False

    def __str__(self) -> str:
        spelled = self.action_id
        if self.occurrence is not None:
            spelled += f"@{self.occurrence}"
        if self.fallback:
            spelled += "/fallback"
        return spelled


class ActionTargets(BaseModel):
    """What an action acts on, by kind of target, which an authorisation
    grant may limit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    devices: frozenset[str] = frozenset()
    plants: frozenset[str] = frozenset()
    targets: frozenset[str] = frozenset()


def targets_of(action: Action) -> ActionTargets:
    """The devices, plants and controller targets an action acts on."""
    match action:
        case SetLevel(device_id=device_id):
            return ActionTargets(devices=frozenset({device_id}))
        case SetTarget(target=target):
            return ActionTargets(targets=frozenset({target}))
        case Water(plant_id=plant) | Harvest(plant_id=plant) | Lower(plant_id=plant):
            return ActionTargets(plants=frozenset({plant}))
        case RemoveLeaf(plant_id=plant) | Inspect(plant_id=plant):
            return ActionTargets(plants=frozenset({plant}))
