"""What a policy may read and do in a run: its capability and goal context
(decision 0061).

A context is built for one principal in one epoch of one run, from the
run's installation, its scenario and its authorisation. It says what a
grower knows of their own greenhouse, and nothing of how the simulated
world works:

- **the observation sources:** each sensor, meter, measurement model and
  controller, the quantities it observes and how often, and where it is.
  Not its noise, drift or faults, which are the simulated world's;
- **the devices,** what each does and the levels it may be set to;
- **the targets,** each with its range and unit. The target in force is
  observed, as its setpoint's observation type, not given here;
- **the crop,** each instance of it (decision 0062): its scope, grown by
  plant or by area, its areas, its plants if it is grown by plant, and the
  crop actions its model takes;
- **when the run carries each kind of action out,** where that is not any
  instant;
- **the gateway's limits** and **the principal's grants;**
- **an experiment's goals and constraints,** each named, with its unit and
  bound.

A policy names its devices, targets and sensors from the context, never by
hand. The record is versioned (`context_version`): a reader that knows an
earlier version reads the fields it knows.
"""

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    StringConstraints,
    field_serializer,
    model_validator,
)

from greenhouse_protocol.actions import ActionKind, ActionTargets, Identifier
from greenhouse_protocol.authorisation import Grant
from greenhouse_protocol.contracts.gateway import GatewayLimits
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.greenhouse import Plant
from greenhouse_protocol.plan import Principal

type Name = Annotated[str, StringConstraints(min_length=1)]

CAPABILITY_CONTEXT_VERSION: Final = 1
# The crop actions, each of which names a plant.
PLANT_ACTIONS: Final = frozenset(
    {
        ActionKind.WATER,
        ActionKind.HARVEST,
        ActionKind.LOWER,
        ActionKind.REMOVE_LEAF,
        ActionKind.INSPECT,
    }
)


def _named_once(kind: str, names: list[str]) -> None:
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(f"{kind} named more than once: {repeated}")


class SourceKind(StrEnum):
    SENSOR = "sensor"  # an instrument, in the house or outside it
    METER = "meter"  # of what the house uses, such as its heat
    MEASUREMENT = "measurement"  # a measurement model's, such as a crop walk (decision 0062)
    CONTROLLER = "controller"  # a climate controller's, of what it was asked


class ObservedQuantity(BaseModel):
    """A quantity a source observes, in the unit its type names, and how
    often: every so many seconds, or None when not at a fixed cadence."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    observation_type: ObservationType
    every_s: PositiveFloat | None = None


class ObservationSource(BaseModel):
    """Where a policy's observations come from: a source by its id, what it
    observes, and where. A source in a compartment may be in one zone of
    it, at one plant, or on one crop instance's scope; none of them for the
    compartment, or the greenhouse, as a whole."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    source_id: Name
    kind: SourceKind
    quantities: Annotated[tuple[ObservedQuantity, ...], Field(min_length=1)]
    compartment_id: Name | None = None
    zone_id: Name | None = None
    plant_id: Name | None = None
    scope_id: Name | None = None

    @model_validator(mode="after")
    def _well_placed(self) -> Self:
        _named_once(
            f"source {self.source_id!r}'s quantities",
            [quantity.observation_type for quantity in self.quantities],
        )
        within = [self.zone_id, self.plant_id, self.scope_id]
        if sum(place is not None for place in within) > 1:
            raise ValueError(
                f"source {self.source_id!r} is in at most one of a zone, a plant and a scope"
            )
        return self


class DeviceControl(BaseModel):
    """A device a policy may set, by `set_level`, the one action on a
    device: what it does, by name, as the installation names it (`heats`,
    `moves_air`, `dries`, `opens`), and the levels it may be given, each a
    share of what it does at full level, or of fully open. `auto` hands it
    back to its control loop, where it has one."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    device_id: Name
    compartment_id: Name | None = None
    does: Annotated[frozenset[Name], Field(min_length=1)]
    low: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    high: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    auto: bool = False

    @field_serializer("does", when_used="json")
    def _in_order(self, does: frozenset[str]) -> list[str]:
        # Written in order, the same context is the same bytes.
        return sorted(does)

    @model_validator(mode="after")
    def _a_range(self) -> Self:
        if self.high < self.low:
            raise ValueError(f"device {self.device_id!r}'s levels end below where they start")
        return self


class TargetControl(BaseModel):
    """A controller's target a policy may set, by `set_target`, its range
    and unit, and the observation type the target in force is observed
    as, when a source observes it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    target: Name
    unit: Name
    low: float
    high: float
    observed_as: ObservationType | None = None

    @model_validator(mode="after")
    def _a_range(self) -> Self:
        if self.high < self.low:
            raise ValueError(f"target {self.target!r}'s range ends below where it starts")
        return self


class CropBasis(StrEnum):
    """How a crop instance is grown, as its model is (decision 0062)."""

    PLANT = "plant"  # plant by plant, each addressed by its id
    AREA = "area"  # as its scope's area, no plant addressed


class CropInstance(BaseModel):
    """An instance of the run's crop: a model on a scope, named by its
    scope (decision 0062). Its areas, in m²: the ground its planting
    positions take, and its share of the house's floor. Its plants, as a
    greenhouse description lists them, only if it is grown by plant; and
    the crop actions its model takes, each of which names a plant."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    scope_id: Name
    # What the scope is, such as a row.
    scope_kind: Name
    grown_by: CropBasis
    cultivated_m2: PositiveFloat
    floor_m2: PositiveFloat
    plants: tuple[Plant, ...] = ()
    crop_actions: frozenset[ActionKind] = frozenset()

    @field_serializer("crop_actions", when_used="json")
    def _in_order(self, kinds: frozenset[ActionKind]) -> list[str]:
        return sorted(kinds)

    @model_validator(mode="after")
    def _plants_with_its_basis(self) -> Self:
        if self.grown_by == CropBasis.AREA and (self.plants or self.crop_actions):
            raise ValueError(
                f"crop instance {self.scope_id!r} is grown by area: it has no plants, "
                "and takes no crop action, each of which names a plant"
            )
        if not self.crop_actions <= PLANT_ACTIONS:
            raise ValueError(
                f"crop instance {self.scope_id!r} takes actions that are not crop actions: "
                f"{sorted(self.crop_actions - PLANT_ACTIONS)}"
            )
        return self


class ActionCadence(BaseModel):
    """The instants at which a run carries a kind of action out: every
    `every_s` seconds from `first_s` after its epoch's start, such as a
    crop's work at the start of each day after the first. A window or an
    as-soon-as-possible action starts at the next; one due at another
    instant is refused."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: ActionKind
    every_s: PositiveFloat
    first_s: NonNegativeFloat = 0.0


class GoalSense(StrEnum):
    MINIMISE = "minimise"
    MAXIMISE = "maximise"
    # A constraint: the measure kept within its bounds.
    WITHIN = "within"


class Goal(BaseModel):
    """An experiment's objective or constraint: what is measured, in which
    unit, and which way, or within which bounds."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    goal_id: Identifier
    description: Name
    unit: Name
    sense: GoalSense
    low: float | None = None
    high: float | None = None

    @model_validator(mode="after")
    def _bounds_with_its_sense(self) -> Self:
        bounded = self.low is not None or self.high is not None
        if (self.sense == GoalSense.WITHIN) != bounded:
            raise ValueError(f"goal {self.goal_id!r} has bounds exactly when it is a constraint")
        if self.low is not None and self.high is not None and self.high < self.low:
            raise ValueError(f"goal {self.goal_id!r}'s bounds end below where they start")
        return self


class CapabilityContext(BaseModel):
    """A principal's context in one epoch of a run: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    context_version: Literal[1] = CAPABILITY_CONTEXT_VERSION
    run_id: Name
    epoch: Annotated[int, Field(ge=0)]
    greenhouse_id: Name
    # Whom it is for: the principal its port gives plans as.
    principal: Principal
    sources: tuple[ObservationSource, ...]
    devices: tuple[DeviceControl, ...]
    targets: tuple[TargetControl, ...]
    crops: tuple[CropInstance, ...]
    # Kinds not listed are carried out at any instant.
    cadences: tuple[ActionCadence, ...] = ()
    limits: GatewayLimits
    # Every grant of every group the principal is in.
    grants: tuple[Grant, ...]
    goals: tuple[Goal, ...] = ()

    @model_validator(mode="after")
    def _each_named_once(self) -> Self:
        _named_once("sources", [source.source_id for source in self.sources])
        _named_once("devices", [device.device_id for device in self.devices])
        _named_once("targets", [target.target for target in self.targets])
        _named_once("crop instances", [crop.scope_id for crop in self.crops])
        _named_once("plants", [plant.plant_id for crop in self.crops for plant in crop.plants])
        _named_once("cadences' kinds", [cadence.kind for cadence in self.cadences])
        _named_once("goals", [goal.goal_id for goal in self.goals])
        return self

    def observed_types(self) -> frozenset[ObservationType]:
        """Every observation type a source of the run observes: those a
        policy reads."""
        return frozenset(
            quantity.observation_type for source in self.sources for quantity in source.quantities
        )

    def items(self) -> ActionTargets:
        """What a policy may act on: the devices, the plants of crops grown
        by plant, and the targets."""
        return ActionTargets(
            devices=frozenset(device.device_id for device in self.devices),
            plants=frozenset(plant.plant_id for crop in self.crops for plant in crop.plants),
            targets=frozenset(target.target for target in self.targets),
        )

    def cadence(self, kind: ActionKind) -> ActionCadence | None:
        return next((cadence for cadence in self.cadences if cadence.kind == kind), None)
