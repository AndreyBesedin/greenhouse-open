"""Observe, decide, act, observe again: a policy on a run.

    python examples/03_close_the_loop.py

A policy steers a run through its port (decision 0061), as its own
principal. It reads its context, what the run's sensors delivered and
what became of the actions it gave, and answers each time with a decision.
An experiment's runner gives the decision to the run's gateway as the next
revision of the policy's plan. The runner moves the run's clock to each
decision, five minutes apart, for two hours: nothing waits, and no clock
is moved by hand.

Here the run is the climate box's, and the policy a naive rule: the heater
on below 15 °C and off above 17 °C, by what a sensor reads, never by the
air itself. It names its heater and its sensor from its context. The
point is the shape of the loop, not the climate.
"""

from datetime import datetime
from typing import Final

from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext, SourceKind
from greenhouse_protocol.contracts.policy import Decision, Delivery, Keep, PolicyIdentity, Revise
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.plan import Asap, PlannedAction, Principal, PrincipalKind
from greenhouse_sim.experiment import Episode, run_episode
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
# What a heater does, as a context names it.
HEATS: Final = "heats"
ON_BELOW_C: Final = 15.0
OFF_ABOVE_C: Final = 17.0
# A decision every five minutes, for two hours.
STEP_S: Final = 300.0
STEPS: Final = 24


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


class NaiveHeating:
    """The rule as a policy: its heater and its sensor from its context, and
    a revision of its plan each time its mind changes."""

    identity: Final = PolicyIdentity(name="naive_heating", version="1")
    decide_every_s: Final = STEP_S

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self._principal = context.principal
        self._heater = next(d.device_id for d in context.devices if HEATS in d.does)
        self._sensor = next(
            source.source_id
            for source in context.sources
            if source.kind == SourceKind.SENSOR
            and source.quantities[0].observation_type == ObservationType.AIR_TEMPERATURE_C
        )
        self._heating = False
        self._changes = 0
        self._first: datetime | None = None

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        self._first = self._first or at
        readings = [o.value for o in delivered.observations if o.sensor_id == self._sensor]
        reads_c = readings[-1] if readings else None
        wanted = decide(reads_c, self._heating)
        reads = "   -   " if reads_c is None else f"{reads_c:4.1f} °C"
        ended = ", ".join(f"{o.ref} {o.status}" for o in delivered.outcomes) or "-"
        print(
            f"{format_time((at - self._first).total_seconds())}  {self._sensor} reads {reads}, "
            f"heater {'on ' if wanted else 'off'}; outcomes: {ended}"
        )
        if wanted == self._heating:
            return Keep()
        self._heating = wanted
        self._changes += 1
        return Revise(
            actions=(
                PlannedAction(
                    action_id=f"{self._heater}_{self._changes}",
                    action=SetLevel(device_id=self._heater, level=1.0 if wanted else 0.0),
                    timing=Asap(),
                    proposed_by=self._principal,
                ),
            )
        )

    def stop(self) -> None:
        self._heating = False


def main() -> None:
    with Simulator(authorisation=AUTHORISATION) as simulator:
        summary = run_episode(
            simulator,
            Episode(
                scenario_id=SCENARIO,
                policy=NaiveHeating(),
                principal=POLICY,
                end_s=STEPS * STEP_S,
            ),
        )
    print(
        f"{summary.decisions} decisions, {len(summary.given)} revisions given, "
        f"{len(summary.outcomes)} outcomes; the episode's digest {summary.digest[:16]}"
    )


if __name__ == "__main__":
    main()
