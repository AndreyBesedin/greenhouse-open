"""A playback's run as the executor of its gateway (P13.3, decision 0046).

A playback holds its run's plans in the protocol's reference gateway
(`greenhouse_protocol.contracts.memory_gateway.InMemoryGateway`), on the
playback's clock, with the run itself as the executor: a `RunExecutor`.
An action the gateway assigns joins the plan the run is worked out under
(`RunExecutor.plan`), from its moment on, and the playback works its
records out again from there. When the clock passes the action's moment it
is done, with its effect, and the gateway writes its outcome; until then it
can be revoked, and leaves the plan. What the run cannot carry out, it
refuses when the action falls due, in its own words.

The run carries out a device's level, a door's or a vent's included, at any
moment of it, and a heating target on the minute, if it has a heating loop.
On an organ crop it carries out a harvest, a lowering, a leaf removed and
an inspection at the start of a day after its first (P13.5), given before
the clock reaches it. It says why it does not carry out the rest, in its
own words (`why_not`), which the gateway gives with its refusal: watering,
for one, since its organ crop has no water in its root zone. It works every
day out ahead of the clock, so its lead time is the whole run: every action
is in its plan as soon as the gateway has it. At one moment, what recurs
comes before what does not, and then each in the order the gateway gave
it. A crop action is done once its day is worked out, with what it did and
the event it made (`carried_out`), as the clock passes its moment.

Who may do what is the simulator's authorisation (decision 0052): a
configuration the server is given as a file (`authorisation_file`), or else
the local operator's, which lets the person at the simulator's own
interface, its viewer and its API, do every kind. The local API knows no
one else: whatever reaches it is the local operator's, and a plan's action
proposed for anyone else is refused unless the configuration grants the
local operator to propose for them. The gateway checks each action when its
plan is given and again when it falls due, and records each change of the
configuration with its moment.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from greenhouse_protocol.actions import Action, ActionKind, ActionTargets
from greenhouse_protocol.assignment import Assignment, ExecutionReport, ReportStatus

# Who may do what, as the protocol writes it: the type the server reads.
from greenhouse_protocol.authorisation import AuthorisationConfig as AuthorisationConfig
from greenhouse_protocol.authorisation import AuthorisationGroup, Grant
from greenhouse_protocol.contracts.execution import AssignmentStatus, Revocation
from greenhouse_protocol.contracts.memory_gateway import effect_of
from greenhouse_protocol.outcome import ActionEffect
from greenhouse_protocol.plan import Principal, PrincipalKind
from pydantic import ValidationError

from greenhouse_sim.climate.commands import TARGET_EVERY_S
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.equipment import Target
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.errors import InvalidRequest, every_reason, first_reason
from greenhouse_sim.services.runs import (
    CROP_KINDS,
    PlannedAt,
    RunPlan,
    crop_model_refusal,
    crop_moment_refusal,
)
from greenhouse_sim.services.scenarios import plant_ids

# The person at the simulator's own interface: its viewer, its API.
LOCAL_OPERATOR: Final = Principal(kind=PrincipalKind.PERSON, id="local_operator")
# Who may do what on a simulator's runs, unless it is given a configuration
# of its own (decision 0052): the local operator, everything.
LOCAL_AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="local_operators",
            principals=frozenset({LOCAL_OPERATOR}),
            grants=(Grant(kinds=frozenset(ActionKind)),),
        ),
    ),
)
# As many actions at once as a run is given: its plan holds them all.
UNLIMITED: Final = 1_000_000

# Why a run refuses an action, or None if it carries it out: the run's own
# check of one action at a moment, in seconds from its start.
type Refusal = Callable[[Action, float], str | None]
# Why a run does not carry out a kind of action, or not at a moment of it,
# in seconds from its start, if given; None if it does.
type Unhonoured = Callable[[ActionKind, float | None], str | None]

# Why the run's organ crop is not watered: its plants have no root zone of
# their own (`greenhouse_sim.biology.plant.environment`).
NO_ROOT_ZONE: Final = (
    "the run's organ crop has no water in its root zone: its plants' water status is always full"
)


def authorisation_file(path: Path) -> AuthorisationConfig:
    """The authorisation a file holds, as the protocol writes it
    (`authorisation.schema.json`): its version, its groups and their
    grants. Refused, saying why, if it cannot be read or is not one."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise InvalidRequest(f"no authorisation read from {path}: {error}") from None
    try:
        return AuthorisationConfig.model_validate_json(text)
    except ValidationError as error:
        raise InvalidRequest(
            f"not an authorisation in {path}: {first_reason(error)}", every_reason(error)
        ) from None


def run_items(config: ScenarioConfig) -> ActionTargets:
    """What a scenario's run has to act on: its equipment, its doors and
    vents, its plants, and its heating loop's targets, if it has one."""
    return ActionTargets(
        devices=frozenset(
            {item.actuator_id for item in config.layout.equipment}
            | {opening.opening_id for opening in config.envelope.openings}
        ),
        plants=frozenset(plant_ids(config)),
        targets=frozenset() if config.thermostat is None else _TARGETS,
    )


def run_kinds(config: ScenarioConfig) -> frozenset[ActionKind]:
    """The kinds of action a scenario's run carries out: levels always,
    targets with a heating loop, and crop actions on an organ crop."""
    kinds = {ActionKind.SET_LEVEL}
    if config.thermostat is not None:
        kinds.add(ActionKind.SET_TARGET)
    if config.crop_model == CropModel.ORGAN:
        kinds |= CROP_KINDS
    return frozenset(kinds)


def run_unhonoured(config: ScenarioConfig) -> Unhonoured:
    """Why a scenario's run does not carry out a kind of action, or not at a
    moment of it, in its own words: see the module."""

    def unhonoured(kind: ActionKind, moment_s: float | None) -> str | None:
        if kind == ActionKind.WATER:
            return crop_model_refusal(config, kind) or NO_ROOT_ZONE
        if kind == ActionKind.SET_TARGET and config.thermostat is None:
            return f"{config.greenhouse_id} has no heating loop to set a target of"
        if kind not in CROP_KINDS:
            return None
        if moment_s is None:
            return crop_model_refusal(config, kind)
        return crop_moment_refusal(config, kind, moment_s)

    return unhonoured


_TARGETS: Final = frozenset(target.value for target in Target)


@dataclass(frozen=True)
class Carried:
    """What the run made of one of its crop actions once its day was worked
    out: what it did and the event it made of it, or why it refused it."""

    effect: ActionEffect | None = None
    event_id: str | None = None
    refusal: str | None = None


@dataclass
class _Held:
    assignment: Assignment
    # Its place among those given: at one moment, the order they apply in.
    given: int
    # Why the run will refuse it when it falls due, if it will.
    refusal: str | None = None
    # What the run made of a crop action, once its day is worked out.
    carried: Carried | None = None
    finished: bool = False
    revoked: bool = False


class RunExecutor:
    """A run as its gateway's executor, on the clock of the playback that
    works it out: see the module. `changed` is told the moment, in seconds
    from the run's start, from which its plan has changed; `refuses` says
    why the run would refuse an action, if it would; and `unhonoured` why it
    does not carry out a kind, or not at a moment (`run_unhonoured`)."""

    def __init__(
        self,
        start: datetime,
        end_s: float,
        *,
        kinds: frozenset[ActionKind],
        changed: Callable[[float], None] = lambda _: None,
        refuses: Refusal = lambda _action, _at: None,
        unhonoured: Unhonoured = lambda _kind, _at: None,
    ) -> None:
        self.now = start
        self._start = start
        self._end_s = end_s
        self._kinds = kinds
        self._changed = changed
        self._refuses = refuses
        self._unhonoured = unhonoured
        self._held: dict[str, _Held] = {}
        self._reports: list[ExecutionReport] = []

    def seconds(self, instant: datetime) -> float:
        """An instant as seconds from the run's start."""
        return (instant - self._start).total_seconds()

    def instant(self, seconds: float) -> datetime:
        """Seconds from the run's start as an instant."""
        return self._start + timedelta(seconds=seconds)

    # The executor contract.

    def kinds(self) -> frozenset[ActionKind]:
        return self._kinds

    def honours(self, kind: ActionKind, instant: datetime) -> bool:
        return self.why_not(kind, instant) is None

    def why_not(self, kind: ActionKind, instant: datetime | None = None) -> str | None:
        """Why the run does not carry out `kind`, or not at `instant`, if
        given, in its own words; None if it does (`ExplainsRefusals`)."""
        if kind not in self._kinds:
            return self._unhonoured(kind, None) or f"the run does not carry out {kind}"
        if instant is None:
            return None
        moment = self.seconds(instant)
        if not 0.0 <= moment <= self._end_s:
            return f"the run lasts from 0 to {self._end_s:.15g} s, not {moment:.15g} s"
        if kind == ActionKind.SET_TARGET and moment % TARGET_EVERY_S != 0:
            return f"the run changes a target on the minute, not at {moment:.15g} s"
        unhonoured = self._unhonoured(kind, moment)
        if unhonoured is not None:
            return unhonoured
        if kind not in CROP_KINDS:
            return None
        if moment % DAY_S != 0 or not 0.0 < moment < self._end_s:
            return f"the run carries out {kind} at the start of a day after its first"
        if instant <= self.now:
            return "the run's clock has reached that day's start: its crop's work then is done"
        return None

    def capacity(self) -> int:
        return UNLIMITED

    def lead_time_s(self, kind: ActionKind) -> float:
        return self._end_s

    def longest_duration_s(self, kind: ActionKind) -> float:
        return 0.0

    def perform(self, assignment: Assignment) -> None:
        if assignment.assignment_id in self._held:
            return
        at = self.seconds(assignment.at)
        refusal = self._refusal(assignment.action, assignment.at)
        self._held[assignment.assignment_id] = _Held(
            assignment, given=len(self._held), refusal=refusal
        )
        if refusal is None:
            self._work_again_from(at)

    def revoke(self, assignment_id: str) -> Revocation:
        held = self._held.get(assignment_id)
        if held is None:
            return Revocation.UNKNOWN
        if held.finished:
            return Revocation.FINISHED
        held.revoked = True
        if held.refusal is None:
            self._work_again_from(self.seconds(held.assignment.at))
        return Revocation.REVOKED

    def status(self, assignment_id: str) -> AssignmentStatus:
        held = self._held.get(assignment_id)
        if held is None:
            return AssignmentStatus.UNKNOWN
        if held.revoked:
            return AssignmentStatus.REVOKED
        if held.finished:
            return AssignmentStatus.FINISHED
        return AssignmentStatus.RECEIVED

    def reports(self, after: int = 0) -> tuple[ExecutionReport, ...]:
        return tuple(self._reports[after:])

    # On the gateway's clock.

    def finishes(self) -> tuple[datetime, ...]:
        return tuple(held.assignment.at for held in self._pending())

    def advance(self, to: datetime) -> None:
        """Each action whose moment the clock has reached is done, as the run
        worked it out, or refused, as the run would; a crop action once its
        day is worked out, and not before."""
        for held in sorted(self._pending(), key=_in_order):
            at = held.assignment.at
            waiting = held.assignment.action.kind in CROP_KINDS and held.carried is None
            if at > to or (held.refusal is None and waiting):
                continue
            held.finished = True
            self._reports.append(_report(held))
        self.now = max(self.now, to)

    # The run's side.

    def crop_actions_on(self, day: int) -> tuple[Assignment, ...]:
        """The crop actions its run carries out at the start of its day
        `day`, as they were assigned, in the order they apply: as the run's
        plan has them (`plan`)."""
        moment = self._start + timedelta(seconds=day * DAY_S)
        return tuple(
            held.assignment
            for held in sorted(self._given(), key=_in_order)
            if held.assignment.at == moment and held.assignment.action.kind in CROP_KINDS
        )

    def carried_out(self, carried: Mapping[str, Carried]) -> None:
        """What its run made of crop actions, by assignment, once their day
        is worked out: each is done, or refused, as the clock passes it."""
        for assignment_id, made in carried.items():
            held = self._held.get(assignment_id)
            if held is not None and not held.finished:
                held.carried = made

    def plan(self) -> RunPlan:
        """The plan its run is worked out under: every action given and not
        revoked or to be refused, each at its moment, in the order they
        apply at one moment."""
        given = sorted(self._given(), key=_in_order)
        return RunPlan(
            actions=tuple(
                PlannedAt(at_s=self.seconds(held.assignment.at), action=held.assignment.action)
                for held in given
            )
        )

    def forget(self) -> None:
        """Forgets every action, as a run started over from its start does:
        its plan is empty again, and its clock at the start."""
        given = [held for held in self._held.values() if not held.revoked and held.refusal is None]
        self._held = {}
        self.now = self._start
        if given:
            self._changed(min(self.seconds(held.assignment.at) for held in given))

    def _given(self) -> list[_Held]:
        """Every action given, and not revoked or to be refused."""
        return [held for held in self._held.values() if not held.revoked and held.refusal is None]

    def _pending(self) -> list[_Held]:
        return [held for held in self._held.values() if not (held.revoked or held.finished)]

    def _refusal(self, action: Action, at: datetime) -> str | None:
        why = self.why_not(action.kind, at)
        if why is not None:
            return why
        return self._refuses(action, self.seconds(at))

    def _work_again_from(self, moment_s: float) -> None:
        """Its run's plan changed from `moment_s` on: what it made of crop
        actions from then is worked out again."""
        for held in self._held.values():
            if not held.finished and self.seconds(held.assignment.at) >= moment_s:
                held.carried = None
        self._changed(moment_s)


def _report(held: _Held) -> ExecutionReport:
    """A held action's report, its moment reached: refused, as the run
    refuses it; or done, with its effect, or what the run made of it."""
    assignment_id, at = held.assignment.assignment_id, held.assignment.at
    refusal = held.refusal or (held.carried.refusal if held.carried is not None else None)
    if refusal is not None:
        return ExecutionReport(
            assignment_id=assignment_id, status=ReportStatus.REFUSED, reason=refusal
        )
    carried = held.carried
    return ExecutionReport(
        assignment_id=assignment_id,
        status=ReportStatus.DONE,
        started_at=at,
        finished_at=at,
        effect=effect_of(held.assignment.action) if carried is None else carried.effect,
        event_id=None if carried is None else carried.event_id,
    )


def _in_order(held: _Held) -> tuple[datetime, bool, int]:
    """At one moment, an occurrence of a recurring action before a one-off,
    then in the order given."""
    return held.assignment.at, held.assignment.ref.occurrence is None, held.given
