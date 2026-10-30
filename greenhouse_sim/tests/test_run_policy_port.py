"""A policy's port on a run played back (P15.3, decision 0061): the
protocol's contract held by its conformance check, through a harness that
steps a playback and delivers records into its logs as its producer does;
and what is the simulator's own: cursors kept apart from the consumer
interface's, the operator's plans unseen, a new epoch's logs started
again."""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Final

import pytest
from greenhouse_protocol.actions import SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.consumer import OutcomeBatch, check_polls
from greenhouse_protocol.contracts.gateway import STARTED_OVER, PlanState, Receipt
from greenhouse_protocol.contracts.policy import (
    POLICY,
    RIVAL,
    Delivered,
    PolicyPort,
    check_policy_port,
    conformance_policy_authorisation,
)
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import ActionKey, At, Plan, PlannedAction, Principal

from greenhouse_sim.services import playback
from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.playback import (
    Playback,
    PlaybackCommand,
    PlaybackState,
    RecordsAfter,
    delivered,
)
from greenhouse_sim.services.policy_port import RunPolicyPort, policy_port
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import DAY_S

# Its run's days cost next to nothing, and it has doors to set.
SCENARIO: Final = "airflow_box"
SECONDS_PER_DAY: Final = 24.0
HOUR: Final = timedelta(hours=1)
# How many times a step works a day out, at the most, before it gives up.
STEPS: Final = 100


class _Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Delivering:
    """A playback, played by a test that steps its clock, whose logs also
    take the records the test delivers: each joins its log once the clock
    reaches its delivery, in delivery order, as its producer's do."""

    def __init__(self, played: Playback, clock: _Clock) -> None:
        self.played = played
        self._clock = clock
        self._pending: list[Observation | Event] = []
        self._epoch = played.state().epoch
        self._observations: list[Observation] = []
        self._events: list[Event] = []
        self._read = {"observations": 0, "events": 0}
        # Once set, the run starts over just after its observations are next
        # read, and is stepped on to this moment of its new epoch.
        self.starts_over_to_s: float | None = None

    def deliver(self, records: Sequence[Delivered]) -> None:
        # The port has no forecast log: its budget names no provider.
        self._pending += [r for r in records if isinstance(r, Observation | Event)]

    def advance(self, to: datetime) -> None:
        """Works the run out to `to` and moves its clock there."""
        target_s = (to - self.played.start).total_seconds()
        for _ in range(STEPS):
            state = self.played.state()
            if state.time_s >= target_s:
                return
            if state.worked_out_s <= state.time_s:
                assert self.played.work_day(int(state.worked_out_s // DAY_S))
            self._clock.now += (target_s - state.time_s) / DAY_S * SECONDS_PER_DAY
        raise AssertionError(f"the run did not reach {to.isoformat()}")

    # What a port reads and gives.

    def state(self) -> PlaybackState:
        return self.played.state()

    def context(self, principal: Principal) -> CapabilityContext:
        return self.played.context(principal)

    def records_after(self, after: int, limit: int) -> RecordsAfter[Observation]:
        state = self._caught_up()
        chosen = tuple(self._observations[after : after + limit])
        more = after + len(chosen) < len(self._observations)
        if self.starts_over_to_s is not None:
            to_s, self.starts_over_to_s = self.starts_over_to_s, None
            self.played.command(PlaybackCommand.RESTART)
            self.advance(self.played.start + timedelta(seconds=to_s))
        return RecordsAfter(records=chosen, next=after + len(chosen), has_more=more, state=state)

    def events_after(self, after: int, limit: int) -> RecordsAfter[Event]:
        state = self._caught_up()
        chosen = tuple(self._events[after : after + limit])
        more = after + len(chosen) < len(self._events)
        return RecordsAfter(records=chosen, next=after + len(chosen), has_more=more, state=state)

    def outcomes_after(self, after: int, limit: int) -> tuple[OutcomeBatch, PlaybackState]:
        return self.played.outcomes_after(after, limit)

    def plan(self, plan_id: str, revision: int | None = None) -> PlanState:
        return self.played.plan(plan_id, revision)

    def submit(self, plan: Plan, *, by: Principal) -> Receipt:
        return self.played.submit(plan, by=by)

    def cancel(self, keys: Sequence[ActionKey], *, by: Principal) -> Receipt:
        return self.played.cancel(keys, by=by)

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int, by: Principal) -> Receipt:
        return self.played.cancel_plan(plan_id, revision=revision, epoch=epoch, by=by)

    def owner_of(self, outcome: ActionOutcome) -> Principal | None:
        return self.played.owner_of(outcome)

    def _caught_up(self) -> PlaybackState:
        state = self.played.state()
        if state.epoch != self._epoch:
            # The run started over: its logs start again, as a producer's do.
            self._epoch, self._observations, self._events = state.epoch, [], []
            self._read = {"observations": 0, "events": 0}
        now = state.simulated_now
        due = [r for r in self._pending if delivered(r) <= now]
        self._pending = [r for r in self._pending if delivered(r) > now]
        observations = self._drained(self.played.records_after, "observations")
        events = self._drained(self.played.events_after, "events")
        self._observations += sorted(
            [*observations, *(r for r in due if isinstance(r, Observation))], key=delivered
        )
        self._events += sorted([*events, *(r for r in due if isinstance(r, Event))], key=delivered)
        return state

    def _drained[R: (Observation, Event)](
        self, read: Callable[[int, int], RecordsAfter[R]], log: str
    ) -> list[R]:
        records: list[R] = []
        while True:
            cut = read(self._read[log], 10**6)
            records += cut.records
            self._read[log] = cut.next
            if not cut.has_more:
                return records


class _Harness(RunPolicyPort):
    """A port on a run a test steps and delivers records to."""

    def __init__(self, run: _Delivering, principal: Principal) -> None:
        super().__init__(run, principal)
        self._delivering = run

    def advance(self, to: datetime) -> None:
        self._delivering.advance(to)

    def deliver(self, records: Sequence[Delivered]) -> None:
        self._delivering.deliver(records)

    def open(self, principal: Principal) -> PolicyPort:
        return RunPolicyPort(self._delivering, principal)


def _port(
    simulator: Simulator,
    scenario_id: str = SCENARIO,
    authorisation: AuthorisationConfig | None = None,
) -> tuple[_Harness, Playback]:
    """A port for `POLICY` on a new playback of a scenario's run, played by
    a test, under the conformance check's authorisation or `authorisation`."""
    clock = _Clock()
    played = Playback(simulator, scenario_id, seconds_per_day=SECONDS_PER_DAY, clock=clock)
    played.authorise(authorisation or conformance_policy_authorisation())
    played.command(PlaybackCommand.PLAY)
    return _Harness(_Delivering(played, clock), POLICY), played


@pytest.mark.parametrize(
    "scenario_id", [SCENARIO, pytest.param("climate_box", marks=pytest.mark.slow)]
)
def test_a_port_on_a_run_keeps_the_contract(simulator: Simulator, scenario_id: str) -> None:
    def make(authorisation: AuthorisationConfig, start: datetime) -> _Harness:
        return _port(simulator, scenario_id, authorisation)[0]

    assert check_policy_port(make, Playback(simulator, scenario_id).start) == []


def test_a_cursor_the_port_never_gave_is_answered_with_nothing(simulator: Simulator) -> None:
    port, played = _port(simulator)
    # Past the walk at noon, the airflow box's only observations.
    port.advance(played.start + 13 * HOUR)

    unknown = port.observations(after=3)
    first = port.observations()

    assert (unknown.after, unknown.next, unknown.observations) == (3, 3, ())
    assert first.observations != ()
    assert port.observations(after=first.next).after == first.next


def test_the_operators_plans_and_their_outcomes_are_not_a_policys(simulator: Simulator) -> None:
    port, played = _port(simulator)
    door = min(device.device_id for device in port.context().devices)
    opened = PlannedAction(
        action_id="open",
        action=SetLevel(device_id=door, level=1.0),
        timing=At(at=played.start + HOUR),
        proposed_by=LOCAL_OPERATOR,
    )
    run = port.run()
    receipt = played.submit(
        Plan(
            plan_id="operators", run_id=run.run_id, epoch=run.epoch, revision=1, actions=(opened,)
        ),
        by=LOCAL_OPERATOR,
    )
    assert receipt.accepted, receipt.errors
    port.advance(played.start + 2 * HOUR)

    assert port.plan("operators") is None
    assert port.outcomes().outcomes == ()
    (operators,) = played.outcomes_after(0, 10)[0].outcomes
    assert operators.plan_id == "operators"


def test_a_new_epoch_starts_the_ports_logs_again(simulator: Simulator) -> None:
    port, played = _port(simulator)
    port.advance(played.start + 13 * HOUR)
    before = port.observations()
    assert before.observations != ()

    played.command(PlaybackCommand.RESTART)
    port.advance(played.start + 13 * HOUR)
    after = port.observations(after=before.next)
    again = port.observations()

    assert (after.epoch, after.observations) == (before.epoch + 1, ())
    assert again.epoch == before.epoch + 1
    assert [o.observation_id for o in again.observations] == [
        o.observation_id for o in before.observations
    ]
    assert check_polls([before, after, again], greenhouse_id=port.run().greenhouse_id) == []


def test_after_a_restart_a_port_gives_its_own_actions_cancelled_and_no_one_elses(
    simulator: Simulator,
) -> None:
    port, played = _port(simulator)
    rival = port.open(RIVAL)
    door = min(device.device_id for device in port.context().devices)
    run = port.run()
    for opened, principal in ((port, POLICY), (rival, RIVAL)):
        later = PlannedAction(
            action_id="open",
            action=SetLevel(device_id=door, level=1.0),
            timing=At(at=played.start + 5 * HOUR),
            proposed_by=principal,
        )
        plan = Plan(
            plan_id=principal.id, run_id=run.run_id, epoch=run.epoch, revision=1, actions=(later,)
        )
        assert opened.submit(plan).accepted
    port.advance(played.start + HOUR)

    played.command(PlaybackCommand.RESTART)

    (mine,) = port.outcomes().outcomes
    assert (mine.plan_id, mine.status, mine.epoch) == (POLICY.id, OutcomeStatus.CANCELLED, 1)
    assert STARTED_OVER in (mine.reason or "")
    assert [o.plan_id for o in rival.outcomes().outcomes] == [RIVAL.id]


def test_a_run_that_starts_over_while_a_port_reads_it_is_read_in_its_new_epoch(
    simulator: Simulator,
) -> None:
    """The run starts over between the port's first read of the run's log
    and its read again from the start: what the port keeps, and the cursors
    it gives, are of the epoch it read last."""
    port, played = _port(simulator)
    port.advance(played.start + 13 * HOUR)
    port._delivering.starts_over_to_s = 13 * HOUR.total_seconds()

    first = port.observations()
    port.advance(played.start + 37 * HOUR)
    then = port.observations(after=first.next)

    assert (first.epoch, then.epoch) == (1, 1)
    assert first.observations != () and then.observations != ()
    assert check_polls([first, then], greenhouse_id=port.run().greenhouse_id) == []


def test_a_port_is_opened_on_a_run_played_back(
    simulator: Simulator, no_playbacks: Callable[[], None]
) -> None:
    playback.start(simulator, SCENARIO, SECONDS_PER_DAY, hold=True)
    run_id = playback.playback(simulator, SCENARIO).run_id

    port = policy_port(simulator.playbacks, run_id, POLICY)

    assert port.run().run_id == run_id
    assert port.context().principal == POLICY
    with pytest.raises(NotFound):
        policy_port(simulator.playbacks, "no-such-run", POLICY)
