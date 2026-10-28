"""Observe, decide, act, observe again: a policy on a run.

    python examples/03_close_the_loop.py

A policy acts on a run as a person in the viewer does, through the run's
gateway (decision 0046). It reads what the run's sensors delivered, and what
became of the actions it gave, through the consumer interface; it gives the
gateway the next revision of its plan when its mind changes; and the run's
clock moves on. Here the run is the climate box played back, its clock moved
by hand five minutes at a time, and the policy a naive rule: the heater on below
15 °C and off above 17 °C, by what a sensor reads, never by the air itself.
The point is the shape of the loop, not the climate.
"""

import tempfile
import time
from pathlib import Path
from typing import Final

from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.plan import Asap, Plan, PlannedAction, Principal, PrincipalKind
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import consumer, playback
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "climate_box"
# The policy is a principal of its own, in a group that may set levels and
# do nothing else.
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="naive_heating")
AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="policies",
            principals=frozenset({POLICY}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
    ),
)
HEATER: Final = "heater"
SENSOR: Final = "temperature_front"
ON_BELOW_C: Final = 15.0
OFF_ABOVE_C: Final = 17.0
# The run plays a simulated day in a day of its clock, which the loop moves
# five minutes at a time, for two hours.
SECONDS_PER_DAY: Final = DAY_S
STEP_S: Final = 300.0
STEPS: Final = 24
WAIT_S: Final = 0.05


class Clock:
    """The seconds a playback reads its moment from, moved by the loop."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def format_time(time_s: float) -> str:
    """A moment of the run as hours and minutes into it."""
    minutes = round(time_s / 60)
    return f"{minutes // 60}:{minutes % 60:02}"


def decide(reads_c: float | None, heating: bool) -> bool:
    """Whether the heater is to run from now: on while the air reads cold,
    off once it reads warm, as it was between the two or with no reading."""
    if reads_c is None:
        return heating
    if reads_c < ON_BELOW_C:
        return True
    if reads_c > OFF_ABOVE_C:
        return False
    return heating


def advance(played: Playback, clock: Clock, time_s: float) -> None:
    """Moves the run to `time_s` into it. A playback's moment follows its
    clock no further than its records are worked out, ahead of the clock
    and again from each change of its plan, such as an action carried out:
    so the clock moves once they reach `time_s`, and again from wherever
    the run stopped short."""
    while (state := played.state()).time_s < time_s:
        if state.worked_out_s < time_s:
            time.sleep(WAIT_S)
            continue
        clock.now += (time_s - state.time_s) / DAY_S * SECONDS_PER_DAY


def main() -> None:
    with (
        tempfile.TemporaryDirectory() as kept,
        Simulator(authorisation=AUTHORISATION) as simulator,
    ):
        clock = Clock()
        run_id = playback.start(
            simulator,
            SCENARIO,
            SECONDS_PER_DAY,
            hold=True,
            clock=clock,
            epochs=Epochs(Path(kept)),
        ).run_id
        played = playback.playback(simulator, SCENARIO)
        played.command(PlaybackCommand.PLAY)
        seen: int | None = None
        ended: int | None = None
        heating, revision = False, 0

        for step in range(1, STEPS + 1):
            advance(played, clock, step * STEP_S)
            # Observe: what the sensors delivered, and what became of the
            # actions given, since the last look.
            observations: list[Observation] = []
            while True:
                delivered = consumer.observations(simulator, run_id, after=seen)
                observations += delivered.observations
                seen = delivered.next
                if not delivered.has_more:
                    break
            outcomes: list[ActionOutcome] = []
            while True:
                resolved = consumer.outcomes(simulator, run_id, after=ended)
                outcomes += resolved.outcomes
                ended = resolved.next
                if not resolved.has_more:
                    break
            readings = [o.value for o in observations if o.sensor_id == SENSOR]
            reads_c = readings[-1] if readings else None
            # Decide, and act: the plan's next revision, when its mind changes.
            wanted = decide(reads_c, heating)
            if wanted != heating:
                revision += 1
                receipt = played.submit(
                    Plan(
                        plan_id="heating",
                        run_id=run_id,
                        epoch=played.state().epoch,
                        revision=revision,
                        actions=(
                            PlannedAction(
                                action_id=f"heater_{revision}",
                                action=SetLevel(device_id=HEATER, level=1.0 if wanted else 0.0),
                                timing=Asap(),
                                proposed_by=POLICY,
                            ),
                        ),
                    ),
                    by=POLICY,
                )
                if not receipt.accepted:
                    raise RuntimeError(f"the plan was refused: {receipt.errors}")
                heating = wanted
            reads = "   -   " if reads_c is None else f"{reads_c:4.1f} °C"
            ended_as = ", ".join(f"{o.ref} {o.status}" for o in outcomes) or "-"
            print(
                f"{format_time(step * STEP_S)}  {SENSOR} reads {reads}, "
                f"heater {'on ' if heating else 'off'}; outcomes: {ended_as}"
            )


if __name__ == "__main__":
    main()
