"""A playback's run as the executor of its gateway (P13.3, decision 0046):
held to the protocol's executor and gateway contracts, its plan made of the
actions the gateway gives it, and a target changed while the run plays
ending in its outcome, which a consumer reads."""

from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import pytest
from greenhouse_protocol.actions import ActionKind, ActionRef, SetLevel, SetTarget
from greenhouse_protocol.assignment import Assignment, ReportStatus
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.contracts.consumer import OutcomeBatch, check_polls
from greenhouse_protocol.contracts.execution import Revocation, check_executor
from greenhouse_protocol.contracts.gateway import check_gateway
from greenhouse_protocol.contracts.memory_gateway import InMemoryGateway
from greenhouse_protocol.outcome import OutcomeStatus, TargetSet
from greenhouse_protocol.plan import ExecutorKind, ExecutorRef

from greenhouse_sim.api.consumer import consumer_respond
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services import playback
from greenhouse_sim.services.gateway import LOCAL_OPERATOR, RunExecutor, run_items, run_kinds
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.runs import CROP_KINDS
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

SCENARIO: Final = "reference_greenhouse"
CONFIG: Final = scenario(PACKAGED, SCENARIO)
START: Final = run_start(PACKAGED, SCENARIO)
HOUR: Final = timedelta(hours=1)
RUN: Final = ExecutorRef(kind=ExecutorKind.SIMULATED_RUN, id="run")
DEVICE: Final = sorted(run_items(CONFIG).devices)[0]
# Every record there is, in one batch.
ALL: Final = 10**6
# More target changes than the protocol's default limit of actions to a plan.
MANY_CHANGES: Final = 120


def _executor(**given: Any) -> RunExecutor:
    return RunExecutor(START, CONFIG.run_length_s(), kinds=run_kinds(CONFIG), **given)


def _assigned(
    assignment_id: str,
    action: SetLevel | SetTarget,
    at_s: float,
    occurrence: int | None = None,
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        run_id="run",
        ref=ActionRef(action_id=assignment_id, occurrence=occurrence),
        action=action,
        at=START + timedelta(seconds=at_s),
    )


def test_a_run_keeps_the_executor_contract() -> None:
    violations = check_executor(
        lambda start: RunExecutor(start, CONFIG.run_length_s(), kinds=run_kinds(CONFIG)),
        START,
        action=SetLevel(device_id=DEVICE, level=1.0),
    )

    assert violations == []


def test_a_gateway_acting_through_a_run_keeps_the_gateway_contract() -> None:
    """The protocol's gateway, with a run as its executor, as a playback
    holds it, held to every scenario of the contract."""

    def make(authorisation: AuthorisationConfig, start: Any) -> InMemoryGateway:
        return InMemoryGateway(
            authorisation,
            start,
            executor=RunExecutor(start, CONFIG.run_length_s(), kinds=run_kinds(CONFIG)),
            executor_ref=RUN,
            items=run_items(CONFIG),
        )

    assert check_gateway(make, START) == []


def test_a_run_carries_out_levels_targets_and_crop_actions_it_has() -> None:
    assert run_kinds(CONFIG) == {ActionKind.SET_LEVEL, ActionKind.SET_TARGET} | CROP_KINDS
    assert run_kinds(scenario(PACKAGED, "climate_box")) == {ActionKind.SET_LEVEL}
    assert run_items(scenario(PACKAGED, "climate_box")).targets == frozenset()
    executor = _executor()
    on_the_minute = START + timedelta(minutes=61)

    assert executor.honours(ActionKind.SET_TARGET, on_the_minute)
    assert not executor.honours(ActionKind.SET_TARGET, on_the_minute + timedelta(seconds=30))
    assert executor.honours(ActionKind.SET_LEVEL, on_the_minute + timedelta(seconds=30))
    assert not executor.honours(ActionKind.SET_LEVEL, START - HOUR)
    assert not executor.honours(ActionKind.HARVEST, on_the_minute)


def test_a_runs_plan_is_what_it_was_given_in_the_order_it_applies() -> None:
    """At one moment, an occurrence of a recurring action comes before a
    one-off, then each in the order given; what is revoked leaves the plan,
    and the run hears from which moment its plan changed each time."""
    moments: list[float] = []
    executor = _executor(changed=moments.append)
    executor.perform(_assigned("first", SetLevel(device_id=DEVICE, level=1.0), HOUR_S))
    executor.perform(_assigned("daily", SetLevel(device_id=DEVICE, level=0.5), HOUR_S, 0))
    executor.perform(_assigned("then", SetLevel(device_id=DEVICE, level=0.0), HOUR_S))
    executor.perform(_assigned("later", SetLevel(device_id=DEVICE, level=0.2), 2 * HOUR_S))

    assert [(each.at_s, each.action) for each in executor.plan().actions] == [
        (HOUR_S, SetLevel(device_id=DEVICE, level=0.5)),
        (HOUR_S, SetLevel(device_id=DEVICE, level=1.0)),
        (HOUR_S, SetLevel(device_id=DEVICE, level=0.0)),
        (2 * HOUR_S, SetLevel(device_id=DEVICE, level=0.2)),
    ]
    assert executor.revoke("later") == Revocation.REVOKED
    assert [each.at_s for each in executor.plan().actions] == [HOUR_S] * 3
    assert moments == [HOUR_S, HOUR_S, HOUR_S, 2 * HOUR_S, 2 * HOUR_S]

    executor.advance(START + 90 * timedelta(minutes=1))
    assert executor.revoke("first") == Revocation.FINISHED
    done = [report for report in executor.reports() if report.status == ReportStatus.DONE]
    assert [report.assignment_id for report in done] == ["daily", "first", "then"]


def test_what_the_run_cannot_do_is_refused_when_it_falls_due() -> None:
    """Refused in the run's own words, and never part of its plan."""
    moments: list[float] = []
    executor = _executor(
        changed=moments.append,
        refuses=lambda action, _: "not that one" if action.kind == ActionKind.SET_LEVEL else None,
    )
    executor.perform(_assigned("vent", SetLevel(device_id=DEVICE, level=1.0), HOUR_S))
    executor.perform(_assigned("warm", SetTarget(target="heating_day", value_c=20.0), HOUR_S))

    assert [each.action.kind for each in executor.plan().actions] == [ActionKind.SET_TARGET]
    assert moments == [HOUR_S]
    executor.advance(START + 2 * HOUR)
    refused = {report.assignment_id: report for report in executor.reports()}["vent"]
    assert (refused.status, refused.reason) == (ReportStatus.REFUSED, "not that one")


@pytest.mark.slow
def test_a_target_changed_while_the_run_plays_ends_in_an_outcome_a_consumer_reads(
    simulator: Simulator, tmp_path: Path
) -> None:
    """Set at 6 h 00 min 30 s, the night's target is the local operator's
    action at 6 h 01: done when the clock passes it, by the run, with its
    effect, in the outcome log a consumer polls. One set for later and still
    pending when the run starts over is cancelled, the first outcome of the
    new epoch."""
    clock = _Clock()
    started = playback.start(
        simulator, SCENARIO, 24.0, clock=clock, hold=True, epochs=Epochs(tmp_path)
    )
    played = playback.playback(simulator, SCENARIO)
    assert played.work_day(0)
    played.command(PlaybackCommand.PLAY)
    clock.now = 6.0 + 30.0 / HOUR_S
    played.set_targets({"heating_night": 22.0})
    path = f"/consumer/v1/runs/{started.run_id}/outcomes"
    polls = [_poll(simulator, path)]
    assert polls[0].outcomes == ()

    assert played.work_day(0)
    clock.now = 7.0
    polls.append(_poll(simulator, f"{path}?after={polls[-1].next}"))
    (done,) = polls[-1].outcomes
    assert (done.status, done.effect, done.principal) == (
        OutcomeStatus.EXECUTED,
        TargetSet(target="heating_night", value_c=22.0),
        LOCAL_OPERATOR,
    )
    done_at_s = 6 * HOUR_S + 60.0
    assert done.resolved_at == START + timedelta(seconds=done_at_s)
    assert done.executor == ExecutorRef(kind=ExecutorKind.SIMULATED_RUN, id=started.run_id)

    clock.now = 8.0
    played.set_targets({"heating_day": 25.0})
    restarted = played.command(PlaybackCommand.RESTART)
    assert restarted.targets == []
    # Its records worked out again from the first change it had made, now
    # the scenario's own run's.
    assert restarted.worked_out_s == done_at_s
    polls.append(_poll(simulator, f"{path}?after={polls[-1].next}"))
    polls.append(_poll(simulator, path))
    (dropped,) = polls[-1].outcomes
    assert (polls[-1].epoch, dropped.status) == (restarted.epoch, OutcomeStatus.CANCELLED)
    assert "started over" in (dropped.reason or "")
    assert check_polls(polls) == []


def _poll(simulator: Simulator, path: str) -> OutcomeBatch:
    answer = consumer_respond(simulator, "GET", path)
    assert answer is not None and answer.status == 200, answer
    return OutcomeBatch.model_validate(answer.body)


class _Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_playback_takes_as_many_target_changes_as_it_is_given(simulator: Simulator) -> None:
    """Each change is a revision of the local operator's plan of them,
    which holds every change of the epoch: past the protocol's default of a
    hundred actions to a plan too."""
    played = Playback(simulator, SCENARIO, seconds_per_day=24.0, clock=_Clock())
    for n in range(MANY_CHANGES):
        played.set_targets({"heating_day": 15.0 + n % 10})

    assert len(played.state().targets) == MANY_CHANGES
