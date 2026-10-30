"""An experiment that steps a run (P15.4, decision 0061): a playback
stepped to a moment in the caller's thread, and a policy steering a run
through its port at the runner's barriers, deterministically when the
policy is, its stale revisions given again, its slow decisions skipped."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import (
    CancelPlan,
    Decision,
    Delivery,
    PolicyIdentity,
    Revise,
)
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import Asap, Plan, PlannedAction, Principal, PrincipalKind

from greenhouse_sim.experiment import Episode, Steering, run_episode
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.playback import Playback, PlaybackCommand
from greenhouse_sim.services.policy_port import RunPolicyPort
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

# Its run's days cost next to nothing, and it has doors to set.
SCENARIO: Final = "airflow_box"
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="doors")
# A principal that may manage plans, and propose for the policy.
MANAGER: Final = Principal(kind=PrincipalKind.PLATFORM, id="manager")
AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="policies",
            principals=frozenset({POLICY}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
        AuthorisationGroup(
            group_id="managers",
            principals=frozenset({MANAGER}),
            grants=(Grant(on_behalf_of=frozenset({POLICY}), manage_plans=True),),
        ),
    ),
)
SIX_HOURS_S: Final = 6 * HOUR_S


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    with Simulator(authorisation=AUTHORISATION) as made:
        yield made


class _Doors:
    """Opens and shuts its first door in turn, at each decision; cancels
    its plan at its `cancel_at`-th."""

    identity: Final = PolicyIdentity(name="doors", version="1")
    decide_every_s: Final = HOUR_S

    def __init__(self, *, cancel_at: int | None = None, level: float = 1.0) -> None:
        self._cancel_at = cancel_at
        self._level = level
        self.stopped = False

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self._door = min(device.device_id for device in context.devices)
        self._decided = 0
        self.stopped = False

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        self._decided += 1
        if self._decided == self._cancel_at:
            return CancelPlan()
        level = self._level if self._decided % 2 else 0.0
        return Revise(actions=(_level(f"door_{self._decided}", self._door, level),))

    def stop(self) -> None:
        self.stopped = True


def _level(action_id: str, device_id: str, level: float) -> PlannedAction:
    return PlannedAction(
        action_id=action_id,
        action=SetLevel(device_id=device_id, level=level),
        timing=Asap(),
        proposed_by=POLICY,
    )


def _episode(policy: _Doors, **fields: object) -> Episode:
    return Episode(
        scenario_id=SCENARIO,
        policy=policy,
        principal=POLICY,
        end_s=SIX_HOURS_S,
        **fields,  # type: ignore[arg-type]
    )


def test_an_episode_decides_at_each_barrier_and_gives_its_plan_as_its_principal(
    simulator: Simulator,
) -> None:
    policy = _Doors()

    summary = run_episode(simulator, _episode(policy))

    assert summary.decisions == 7
    assert [given.receipt.revision for given in summary.given] == list(range(1, 8))
    assert all(given.receipt.accepted for given in summary.given)
    assert [given.at - summary.given[0].at for given in summary.given] == [
        timedelta(hours=hour) for hour in range(7)
    ]
    assert [(str(o.ref), o.status, o.principal) for o in summary.outcomes] == [
        (f"door_{n}", OutcomeStatus.EXECUTED, POLICY) for n in range(1, 8)
    ]
    assert (summary.policy, summary.principal, summary.skipped) == (policy.identity, POLICY, ())
    assert policy.stopped


def test_the_same_policy_on_the_same_scenario_gives_the_same_episode(
    simulator: Simulator,
) -> None:
    first = run_episode(simulator, _episode(_Doors()))
    again = run_episode(simulator, _episode(_Doors()))
    other = run_episode(simulator, _episode(_Doors(level=0.5)))

    assert again.digest == first.digest
    assert again.model_dump(exclude={"digest"}) == first.model_dump(exclude={"digest"})
    assert other.digest != first.digest


def test_a_decision_past_its_compute_budget_is_skipped_and_recorded(
    simulator: Simulator,
) -> None:
    ticks = iter(float(tick) for tick in range(1000))

    summary = run_episode(
        simulator, _episode(_Doors(), compute_budget_s=0.5), timer=lambda: next(ticks)
    )

    assert summary.given == ()
    assert [skip.took_s for skip in summary.skipped] == [1.0] * summary.decisions
    assert summary.outcomes == ()


def test_a_policy_that_cancels_its_plan_has_what_was_left_of_it_cancelled(
    simulator: Simulator,
) -> None:
    summary = run_episode(simulator, _episode(_Doors(cancel_at=3)))

    cancelled = summary.given[2].receipt
    assert cancelled.accepted and cancelled.plan_id == "policy"
    assert summary.decisions == 7


def test_a_revision_refused_as_stale_is_given_after_the_one_in_force(
    simulator: Simulator,
) -> None:
    played = Playback(simulator, SCENARIO)
    port = RunPolicyPort(played, POLICY)
    steering = Steering(port, "policy")
    door = min(device.device_id for device in port.context().devices)
    assert steering.revise((_level("open", door, 1.0),)).revision == 1
    run = port.run()
    managed = played.submit(
        Plan(
            plan_id="policy",
            run_id=run.run_id,
            epoch=run.epoch,
            revision=2,
            actions=(_level("shut", door, 0.0),),
        ),
        by=MANAGER,
    )
    assert managed.accepted, managed.errors

    receipt = steering.revise((_level("half", door, 0.5),))

    assert (receipt.accepted, receipt.revision) == (True, 3)
    in_force = port.plan("policy")
    assert in_force is not None and in_force.plan.revision == 3


def test_a_playback_is_stepped_to_a_moment_and_no_further(simulator: Simulator) -> None:
    played = Playback(simulator, SCENARIO)

    state = played.step_to(3 * HOUR_S)

    assert (state.time_s, state.simulated_now) == (
        3 * HOUR_S,
        played.start + timedelta(hours=3),
    )
    with pytest.raises(InvalidRequest, match="steps on from 10800"):
        played.step_to(HOUR_S)
    with pytest.raises(InvalidRequest, match="not to"):
        played.step_to(played.end_s + 1)
    played.command(PlaybackCommand.PLAY)
    with pytest.raises(Conflict, match="plays or works on its own"):
        played.step_to(4 * HOUR_S)
