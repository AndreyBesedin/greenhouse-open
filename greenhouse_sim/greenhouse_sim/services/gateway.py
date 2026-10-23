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
moment of it, and a heating target on the minute, if it has a heating loop;
crop actions wait for P13.5. It works every day out ahead of the clock, so
its lead time is the whole run: every action is in its plan as soon as the
gateway has it. At one moment, what recurs comes before what does not, and
then each in the order the gateway gave it.

Until authorisation is given its own configuration (P13.4), the local
operator, the person at the simulator's own interface, may do every kind.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from greenhouse_protocol.actions import Action, ActionKind, ActionTargets
from greenhouse_protocol.assignment import Assignment, ExecutionReport, ReportStatus
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.contracts.execution import AssignmentStatus, Revocation
from greenhouse_protocol.contracts.memory_gateway import effect_of
from greenhouse_protocol.plan import Principal, PrincipalKind

from greenhouse_sim.climate.commands import TARGET_EVERY_S
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.runs import PlannedAt, RunPlan
from greenhouse_sim.services.scenarios import plant_ids

# The person at the simulator's own interface: its viewer, its API.
LOCAL_OPERATOR: Final = Principal(kind=PrincipalKind.PERSON, id="local_operator")
# Who may do what on a simulator's runs, until P13.4 makes it a run's own
# configuration: the local operator, everything.
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
    """The kinds of action a scenario's run carries out."""
    if config.thermostat is None:
        return frozenset({ActionKind.SET_LEVEL})
    return frozenset({ActionKind.SET_LEVEL, ActionKind.SET_TARGET})


_TARGETS: Final = frozenset({"heating_day", "heating_night"})


@dataclass
class _Held:
    assignment: Assignment
    # Its place among those given: at one moment, the order they apply in.
    given: int
    # Why the run will refuse it when it falls due, if it will.
    refusal: str | None = None
    finished: bool = False
    revoked: bool = False


class RunExecutor:
    """A run as its gateway's executor, on the clock of the playback that
    works it out: see the module. `changed` is told the moment, in seconds
    from the run's start, from which its plan has changed, and `refuses`
    says why the run would refuse an action, if it would."""

    def __init__(
        self,
        start: datetime,
        end_s: float,
        *,
        kinds: frozenset[ActionKind],
        changed: Callable[[float], None] = lambda _: None,
        refuses: Refusal = lambda _action, _at: None,
    ) -> None:
        self.now = start
        self._start = start
        self._end_s = end_s
        self._kinds = kinds
        self._changed = changed
        self._refuses = refuses
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
        moment = self.seconds(instant)
        on_time = kind != ActionKind.SET_TARGET or moment % TARGET_EVERY_S == 0
        return kind in self._kinds and 0.0 <= moment <= self._end_s and on_time

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
            self._changed(at)

    def revoke(self, assignment_id: str) -> Revocation:
        held = self._held.get(assignment_id)
        if held is None:
            return Revocation.UNKNOWN
        if held.finished:
            return Revocation.FINISHED
        held.revoked = True
        if held.refusal is None:
            self._changed(self.seconds(held.assignment.at))
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
        worked it out, or refused, as the run would."""
        for held in sorted(self._pending(), key=_in_order):
            at = held.assignment.at
            if at > to:
                continue
            held.finished = True
            if held.refusal is not None:
                report = ExecutionReport(
                    assignment_id=held.assignment.assignment_id,
                    status=ReportStatus.REFUSED,
                    reason=held.refusal,
                )
            else:
                report = ExecutionReport(
                    assignment_id=held.assignment.assignment_id,
                    status=ReportStatus.DONE,
                    started_at=at,
                    finished_at=at,
                    effect=effect_of(held.assignment.action),
                )
            self._reports.append(report)
        self.now = max(self.now, to)

    # The run's side.

    def plan(self) -> RunPlan:
        """The plan its run is worked out under: every action given and not
        revoked or to be refused, each at its moment, in the order they
        apply at one moment."""
        given = sorted(
            (held for held in self._held.values() if not held.revoked and held.refusal is None),
            key=_in_order,
        )
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

    def _pending(self) -> list[_Held]:
        return [held for held in self._held.values() if not (held.revoked or held.finished)]

    def _refusal(self, action: Action, at: datetime) -> str | None:
        moment = self.seconds(at)
        if not self.honours(action.kind, at):
            return f"the run does not carry out {action.kind} at {moment:.15g} s"
        return self._refuses(action, moment)


def _in_order(held: _Held) -> tuple[datetime, bool, int]:
    """At one moment, an occurrence of a recurring action before a one-off,
    then in the order given."""
    return held.assignment.at, held.assignment.ref.occurrence is None, held.given
