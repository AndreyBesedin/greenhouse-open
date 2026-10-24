"""A run as a client asks for it, the plan it carries out, and its moments
as the services check them (P09.2): from its start to the end of its
scenario's last day, on the run's clock (`greenhouse_sim.core.clock`)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Final, Self, cast

from greenhouse_protocol.actions import (
    ActionKind,
    Harvest,
    Inspect,
    Lower,
    RemoveLeaf,
    SetLevel,
    SetTarget,
)
from pydantic import BaseModel, ConfigDict, Field

from greenhouse_sim.core.clock import DAY_S, day_start
from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.scenarios import plant_ids

# A command as a request writes it: its moment, its actuator and its level.
# A daily command's moment is its time of day; a target change's actuator is
# its target, and its level the value it sets, in °C (#274).
type Commanded = tuple[float, str, float]

# The kinds of action a run carries out on its organ crop (P13.5), at the
# start of a day after its first: the crop steps a day at a time.
CROP_KINDS: Final = frozenset(
    {ActionKind.HARVEST, ActionKind.LOWER, ActionKind.REMOVE_LEAF, ActionKind.INSPECT}
)

# An action of the kinds a run carries out.
type RunAction = Annotated[
    SetLevel | SetTarget | Harvest | Lower | RemoveLeaf | Inspect, Field(discriminator="kind")
]


class PlannedAt(BaseModel):
    """An action of a run's plan, at a moment of the run: seconds from its
    start."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    at_s: float
    action: RunAction


class PlannedDaily(BaseModel):
    """A device's level that a run's plan sets every day of the run, at a
    time of day: seconds from its midnight."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    time_of_day_s: float
    action: SetLevel


# A run's crop actions that act on its crop, by their moments
# (`RunPlan.crop_plan`): what tells its crop from another's of the same air.
type CropPlan = tuple[PlannedAt, ...]


class RunPlan(BaseModel):
    """What a run is asked to do once it has started (P13.2, decision 0046),
    in the protocol's actions of the kinds a run carries out: a device's
    level, a door's or a vent's included, a heating target and, on an organ
    crop, a harvest, a lowering, a leaf removed and an inspection, at the
    start of a day (`CROP_KINDS`, P13.5).

    - `actions`: each at its moment, in the order given, those at one
      moment included;
    - `daily`: a device's levels every day, or None for its scenario's
      standing plan (its manifest's daily commands), apart from an empty
      tuple, which is nothing every day.

    At one moment, what a run does every day comes before what it does that
    day alone, as a gateway orders recurring actions before one-off ones;
    and at one moment, a later level for a device is the one it keeps.
    Where the run starts from, its devices' levels and its doors' and
    vents' openings, is its request's, not its plan's: an action at the
    run's start is one more after them."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    actions: tuple[PlannedAt, ...] = ()
    daily: tuple[PlannedDaily, ...] | None = None

    @classmethod
    def requested(
        cls,
        commands: Sequence[Commanded] = (),
        daily: Sequence[Commanded] | None = None,
        targets: Sequence[Commanded] = (),
    ) -> RunPlan:
        """A plan as a request writes it (`&schedule=`, `&daily=`,
        `&targets=`), each value as it is given: unchecked, since a run
        checks the plan it is given before it carries it out
        (`climate_runs.checked_commands`, `checked_targets`), and refuses
        what it cannot do in its own words."""
        levels = (
            PlannedAt.model_construct(at_s=moment, action=_level(device, level))
            for moment, device, level in commands
        )
        changes = (
            PlannedAt.model_construct(at_s=moment, action=_target(target, value))
            for moment, target, value in targets
        )
        each_day = (
            None
            if daily is None
            else tuple(
                PlannedDaily.model_construct(time_of_day_s=time, action=_level(device, level))
                for time, device, level in daily
            )
        )
        return cls.model_construct(actions=(*levels, *changes), daily=each_day)

    def commanded(self) -> tuple[Commanded, ...]:
        """Its devices' levels at their moments, as a request writes them,
        in the order given."""
        return tuple(
            (planned.at_s, planned.action.device_id, _commanded_level(planned.action))
            for planned in self.actions
            if isinstance(planned.action, SetLevel)
        )

    def daily_commanded(self) -> tuple[Commanded, ...] | None:
        """Its devices' levels every day, as a request writes them; None for
        its scenario's own."""
        if self.daily is None:
            return None
        return tuple(
            (planned.time_of_day_s, planned.action.device_id, _commanded_level(planned.action))
            for planned in self.daily
        )

    def targeted(self) -> tuple[Commanded, ...]:
        """Its target changes, as a request writes them, in the order given."""
        return tuple(
            (planned.at_s, planned.action.target, planned.action.value_c)
            for planned in self.actions
            if isinstance(planned.action, SetTarget)
        )

    def cropped(self) -> tuple[PlannedAt, ...]:
        """Its crop actions, each at its moment, in the order given."""
        return tuple(planned for planned in self.actions if planned.action.kind in CROP_KINDS)

    def crop_plan(self) -> CropPlan:
        """Its crop actions that act on its crop, its harvests, lowerings
        and leaves removed, by their moments, those at one moment in the
        order given."""
        worked = (each for each in self.cropped() if not isinstance(each.action, Inspect))
        return tuple(sorted(worked, key=lambda each: each.at_s))

    def before(self, moment_s: float) -> Self:
        """The plan as it stood for what came before `moment_s`: its actions
        at earlier moments, its crop actions at that moment too, since the
        crop at a day's start is the crop once that day's work is done; and
        what it does every day."""
        return self.model_copy(
            update={
                "actions": tuple(
                    each
                    for each in self.actions
                    if each.at_s < moment_s
                    or (each.at_s == moment_s and each.action.kind in CROP_KINDS)
                )
            }
        )

    def validated(self) -> Self:
        """The plan with each action held to the protocol's own rules, its
        numbers as the protocol writes them; refused, as the protocol
        refuses, if one breaks them."""
        # As a request wrote them, its numbers may not be the floats the
        # protocol's fields are typed with until they are validated.
        return type(self).model_validate(self.model_dump(warnings=False))


def crop_moment_refusal(config: ScenarioConfig, kind: ActionKind, at_s: float) -> str | None:
    """Why a run of a scenario does not carry out a crop action of `kind` at
    `at_s` seconds from its start, if it does not: its organ crop steps a
    day at a time, and its work begins with its second day."""
    if config.crop_model != CropModel.ORGAN:
        return (
            f"{config.greenhouse_id} grows its crop with the simple daily model, "
            f"which takes no {kind}"
        )
    if at_s % DAY_S != 0:
        return (
            f"the run's crop steps a day at a time: it carries out {kind} at a day's start, "
            f"not at {at_s:.15g} s"
        )
    if at_s <= 0:
        return "the run's crop is planted at its start: its work begins with its second day"
    if at_s >= config.run_length_s():
        return f"the run ends at {config.run_length_s():.15g} s: no day of it starts then"
    return None


def crop_action_refusal(config: ScenarioConfig, action: CropAction | Inspect) -> str | None:
    """Why a run of a scenario does not carry out a crop action on a plant,
    whatever the day, if it does not: a plant it has not, or a lowering to a
    head room on a plant that hangs from no wire."""
    plants = plant_ids(config)
    if action.plant_id not in plants:
        return f"{config.greenhouse_id} has no plant {action.plant_id!r}"
    if isinstance(action, Lower) and action.to_head_room_m is not None:
        trainings = dict(zip(plants, config.layout.trainings(), strict=False))
        training = trainings.get(action.plant_id)
        if training is None or training.wire_m is None:
            return f"{action.plant_id} hangs from no wire"
    return None


def checked_crop_plan(config: ScenarioConfig, plan: RunPlan) -> CropPlan:
    """A run's crop plan (`RunPlan.crop_plan`), of a scenario as `config`
    has it; refused, saying why, if the run would not carry out one of its
    crop actions."""
    cropped = plan.cropped()
    for planned in cropped:
        match planned.action:
            case Harvest() | Lower() | RemoveLeaf() | Inspect() as action:
                refusal = crop_moment_refusal(
                    config, action.kind, planned.at_s
                ) or crop_action_refusal(config, action)
                if refusal is not None:
                    raise InvalidRequest(refusal)
    return plan.crop_plan()


def crop_days(planned: CropPlan) -> dict[int, tuple[CropAction, ...]]:
    """A crop plan's actions by the day they start, each day's in order."""
    days: dict[int, tuple[CropAction, ...]] = {}
    for each in planned:
        match each.action:
            case Harvest() | Lower() | RemoveLeaf() as action:
                day = int(each.at_s // DAY_S)
                days[day] = (*days.get(day, ()), action)
    return days


def _level(device_id: str, level: float) -> SetLevel:
    return SetLevel.model_construct(device_id=device_id, level=level)


def _target(name: str, value_c: float) -> SetTarget:
    # Any name, as a request writes it: the run refuses a target it has not.
    return SetTarget.model_construct(target=cast("Any", name), value_c=value_c)


def _commanded_level(action: SetLevel) -> float:
    if action.level == "auto":
        raise InvalidRequest(
            f"a run sets {action.device_id}'s level from 0 to 1; it does not yet hand a "
            "device back to its control loop (auto)"
        )
    return action.level


@dataclass(frozen=True)
class RunRequest:
    """A scenario's run as a client asks for it (audit W11, `AUDIT.6`), read
    once by the API and taken by every service that runs one:

    - its scenario, one of its layouts and a weather, each by name, or its
      own when None;
    - its equipment's levels and its doors' and vents' openings from the
      start, by identifier: where it starts from;
    - its plan: what it does once it has started (`RunPlan`).

    It names a run, and nothing of what is asked of it: the moment drawn and
    a series' window are the services' own arguments, so the runs kept are
    told apart without them. Each service checks it as it always has: a
    layout, a weather or a piece of equipment the scenario does not have is
    refused there, not here."""

    scenario_id: str
    layout: str | None = None
    weather: str | None = None
    levels: Mapping[str, float] = field(default_factory=dict)
    openings: Mapping[str, float] = field(default_factory=dict)
    plan: RunPlan = field(default_factory=RunPlan)


def checked_moment(config: ScenarioConfig, time_s: float) -> float:
    """A moment of a scenario's run, refused if the run does not reach it."""
    length = config.run_length_s()
    if not 0.0 <= time_s <= length:
        raise InvalidRequest(
            f"a run of {config.greenhouse_id} lasts from 0 to {length:.15g} s, its "
            f"{config.duration_days} days, not {time_s:.15g}"
        )
    return time_s


def checked_window(config: ScenarioConfig, from_s: float | None, until_s: float) -> float:
    """Where a series up to `until_s` begins: at `from_s` if asked, or else
    at the start of the day `until_s` belongs to, so that a series is a
    day's at most unless a longer one is asked for. Refused if `until_s` or
    `from_s` lies outside the run, or `from_s` after `until_s`."""
    checked_moment(config, until_s)
    if from_s is None:
        return day_start(until_s)
    checked_moment(config, from_s)
    if from_s > until_s:
        raise InvalidRequest(
            f"a series runs from {from_s:.15g} s to no earlier, not {until_s:.15g}"
        )
    return from_s
