"""An experiment that steps a run (P15.4, decision 0061): a playback
stepped to a moment in the caller's thread, and a policy steering a run
through its port at the runner's barriers, deterministically when the
policy is, its stale revisions given again, its slow decisions skipped."""

from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import (
    OBSERVATIONS_ONLY,
    ForecastProvider,
    ForecastUncertainty,
    InformationBasis,
    InformationBudget,
)
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import (
    CancelPlan,
    Decision,
    Delivery,
    PolicyIdentity,
    Revise,
)
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import Asap, At, Plan, PlannedAction, Principal, PrincipalKind

from greenhouse_sim.experiment import Episode, Steering, run_episode
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.playback import Playback, PlaybackCommand
from greenhouse_sim.services.policy_port import RunPolicyPort
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import DAY_S, HOUR_S

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
    """Opens and shuts its first door in turn, at each decision, every
    `every_s`, `later_s` after it decides; cancels its plan at its
    `cancel_at`-th decision."""

    identity: Final = PolicyIdentity(name="doors", version="1")

    def __init__(
        self,
        *,
        cancel_at: int | None = None,
        level: float = 1.0,
        every_s: float = HOUR_S,
        later_s: float | None = None,
    ) -> None:
        self._cancel_at = cancel_at
        self._level = level
        self.decide_every_s = every_s
        self._later = None if later_s is None else timedelta(seconds=later_s)
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
        timing = Asap() if self._later is None else At(at=at + self._later)
        return Revise(actions=(_level(f"door_{self._decided}", self._door, level, timing),))

    def stop(self) -> None:
        self.stopped = True


def _level(
    action_id: str, device_id: str, level: float, timing: Asap | At | None = None
) -> PlannedAction:
    return PlannedAction(
        action_id=action_id,
        action=SetLevel(device_id=device_id, level=level),
        timing=timing or Asap(),
        proposed_by=POLICY,
    )


def _episode(policy: _Doors, *, end_s: float = SIX_HOURS_S, **fields: object) -> Episode:
    return Episode(
        scenario_id=SCENARIO,
        policy=policy,
        principal=POLICY,
        end_s=end_s,
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


class _Foresight:
    """A forecaster of the run's future truth: one forecast of the outside
    air's temperature at each moment it is asked, for the hour after."""

    provider = ForecastProvider(
        provider_id="foresight",
        version="1",
        basis=InformationBasis.PRIVILEGED,
        quantities=frozenset({ObservationType.OUTSIDE_AIR_TEMPERATURE_C}),
        issued_every_s=HOUR_S,
        horizon_s=HOUR_S,
        uncertainty=ForecastUncertainty.NONE,
    )

    def issue_due(
        self,
        observed: Sequence[Observation],
        *,
        start: datetime,
        greenhouse_id: str,
        after: datetime | None,
        until: datetime,
    ) -> list[Forecast]:
        return [
            Forecast(
                forecast_id=f"foresight-{int((until - start).total_seconds())}",
                greenhouse_id=greenhouse_id,
                provider_id="foresight",
                provider_version="1",
                issued_at=until,
                valid_from=until,
                valid_until=until + timedelta(hours=1),
                quantity=ObservationType.OUTSIDE_AIR_TEMPERATURE_C,
                value=20.0,
            )
        ]


def test_an_episode_says_what_it_gave_its_policy_and_an_oracle_is_labelled(
    simulator: Simulator,
) -> None:
    oracle = InformationBudget(budget_id="foresight", forecasts=(_Foresight.provider,), oracle=True)

    given = run_episode(simulator, _episode(_Doors(), budget=oracle), forecasters=(_Foresight(),))
    plain = run_episode(simulator, _episode(_Doors()))

    assert (given.budget, given.budget.oracle) == (oracle, True)
    assert (plain.budget, plain.budget.oracle) == (OBSERVATIONS_ONLY, False)
    assert given.digest != plain.digest
    # A run is not given a budget that names a provider it does not serve.
    with pytest.raises(InvalidRequest, match="no forecaster serves"):
        run_episode(simulator, _episode(_Doors(), budget=oracle))


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


def test_a_playback_stepped_to_its_start_delivers_what_is_read_then() -> None:
    with Simulator() as fresh:
        played = Playback(fresh, "sensor_lab")

        played.step_to(0.0)

        readings = played.records_after(0, 10**6).records
        assert readings
        assert {reading.timestamp for reading in readings} == {played.start}


def test_an_episode_runs_to_its_end_between_decisions(simulator: Simulator) -> None:
    """Decided at 0 and 60 minutes, for 15 minutes later each, an episode
    of 90 minutes carries both actions out."""
    summary = run_episode(
        simulator,
        Episode(
            scenario_id=SCENARIO,
            policy=_Doors(later_s=15 * 60.0),
            principal=POLICY,
            end_s=90 * 60.0,
        ),
    )

    assert summary.decisions == 2
    assert [(str(o.ref), o.status) for o in summary.outcomes] == [
        ("door_1", OutcomeStatus.EXECUTED),
        ("door_2", OutcomeStatus.EXECUTED),
    ]


def test_an_episode_as_long_as_its_run_decides_up_to_its_end(simulator: Simulator) -> None:
    run_s = Playback(simulator, SCENARIO).end_s

    summary = run_episode(
        simulator,
        Episode(scenario_id=SCENARIO, policy=_Doors(every_s=DAY_S), principal=POLICY, end_s=run_s),
    )

    assert summary.decisions == round(run_s / DAY_S)
    assert all(given.receipt.accepted for given in summary.given)


@pytest.mark.parametrize("every_s", [0.0, -1.0, 1e-9, float("inf"), float("nan")])
def test_a_cadence_that_would_not_move_the_clock_is_refused(
    simulator: Simulator, every_s: float
) -> None:
    with pytest.raises(ValueError, match="more than none"):
        run_episode(simulator, _episode(_Doors(every_s=every_s)))


def test_an_episode_past_its_run_is_refused(simulator: Simulator) -> None:
    run_s = Playback(simulator, SCENARIO).end_s

    with pytest.raises(ValueError, match="ends within its run"):
        run_episode(simulator, _episode(_Doors(), end_s=run_s + 1))


def test_a_plan_a_manager_revised_is_cancelled_as_it_stands(simulator: Simulator) -> None:
    played = Playback(simulator, SCENARIO)
    port = RunPolicyPort(played, POLICY)
    steering = Steering(port, "policy")
    door = min(device.device_id for device in port.context().devices)
    later = At(at=played.start + timedelta(hours=3))
    steering.revise((_level("open", door, 1.0, later),))
    run = port.run()
    played.submit(
        Plan(
            plan_id="policy",
            run_id=run.run_id,
            epoch=run.epoch,
            revision=2,
            actions=(_level("shut", door, 0.0, later),),
        ),
        by=MANAGER,
    )

    receipt = steering.cancel()

    assert receipt is not None and receipt.accepted, receipt
    assert [ref.action_id for ref in receipt.cancelled] == ["shut"]
