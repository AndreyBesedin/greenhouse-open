"""A run as a client asks for it, the plan it carries out, and its moments
as the services check them (P09.2): from its start to the end of its
scenario's last day, on the run's clock (`greenhouse_sim.core.clock`)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Self, cast

from greenhouse_protocol.actions import SetLevel, SetTarget
from pydantic import BaseModel, ConfigDict, Field

from greenhouse_sim.core.clock import day_start
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.errors import InvalidRequest

# A command as a request writes it: its moment, its actuator and its level.
# A daily command's moment is its time of day; a target change's actuator is
# its target, and its level the value it sets, in °C (#274).
type Commanded = tuple[float, str, float]


class PlannedAt(BaseModel):
    """An action of a run's plan, at a moment of the run: seconds from its
    start."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at_s: float
    action: Annotated[SetLevel | SetTarget, Field(discriminator="kind")]


class PlannedDaily(BaseModel):
    """A device's level that a run's plan sets every day of the run, at a
    time of day: seconds from its midnight."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_of_day_s: float
    action: SetLevel


class RunPlan(BaseModel):
    """What a run is asked to do once it has started (P13.2, decision 0046),
    in the protocol's actions of the kinds a run carries out: a device's
    level, a door's or a vent's included, and a heating target.

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

    model_config = ConfigDict(frozen=True, extra="forbid")

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

    def before(self, moment_s: float) -> Self:
        """The plan as it stood for what came before `moment_s`: its actions
        at earlier moments, and what it does every day."""
        return self.model_copy(
            update={"actions": tuple(each for each in self.actions if each.at_s < moment_s)}
        )

    def validated(self) -> Self:
        """The plan with each action held to the protocol's own rules, its
        numbers as the protocol writes them; refused, as the protocol
        refuses, if one breaks them."""
        return type(self).model_validate(self.model_dump())


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
