"""Example 03's rule as an experiment makes a policy: from its settings.

Not an example of its own, but the policy example 06 runs, by its factory
`naive_heating:NaiveHeating`. An experiment's runner imports a factory by
its module's name, so the module is one Python can import, from this
folder: `python examples/06_run_an_experiment.py` finds it beside itself,
and `python -m greenhouse_sim.experiment` from this folder, or with it on
`PYTHONPATH`.

The rule is example 03's, the heater on below one temperature and off
above another, but the two are its settings, its band, rather than fixed:
`{"on_below_c": 15.0, "off_above_c": 17.0}` is example 03's, and gives the
run example 03 gives it. The rule draws nothing, so it takes no seed.
"""

from datetime import datetime
from typing import Final

from greenhouse_protocol.actions import SetLevel
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext, SourceKind
from greenhouse_protocol.contracts.policy import Decision, Delivery, Keep, PolicyIdentity, Revise
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.plan import Asap, PlannedAction
from pydantic import JsonValue

# What a heater does, as a context names it.
HEATS: Final = "heats"
# A decision every five minutes.
STEP_S: Final = 300.0


def _degrees(settings: dict[str, JsonValue], name: str) -> float:
    value = settings.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"the rule's {name} is a temperature in °C, not {value!r}")
    return float(value)


class NaiveHeating:
    """The rule, its heater and its sensor from its context, and a revision
    of its plan each time its mind changes."""

    identity: Final = PolicyIdentity(name="naive_heating", version="1")
    decide_every_s: Final = STEP_S

    def __init__(self, settings: dict[str, JsonValue], seed: int | None) -> None:
        if seed is not None:
            raise ValueError("the rule draws nothing: it takes no seed")
        self._on_below_c = _degrees(settings, "on_below_c")
        self._off_above_c = _degrees(settings, "off_above_c")
        if self._on_below_c >= self._off_above_c:
            raise ValueError("the rule turns its heater on below a temperature lower than off")

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

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        readings = [o.value for o in delivered.observations if o.sensor_id == self._sensor]
        wanted = self._wanted(readings[-1] if readings else None)
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

    def _wanted(self, reads_c: float | None) -> bool:
        """Whether the heater is to run from now: on while the air reads
        cold, off once it reads warm, as it was between the two or with no
        reading."""
        if reads_c is None:
            return self._heating
        if reads_c < self._on_below_c:
            return True
        if reads_c > self._off_above_c:
            return False
        return self._heating
