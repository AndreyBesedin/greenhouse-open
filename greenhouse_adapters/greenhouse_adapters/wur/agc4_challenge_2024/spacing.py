"""Plant spacing in the 2024 compartments.

Every compartment starts at 56 plants/m2 and is re-spaced to lower densities
on team-specific dates. The time series records the density only on the day
it takes effect (local midnight). The density itself is a compartment-level
observation - the current state - and each change after the first recorded
value is also a SPACING event - the intervention that caused it."""

from collections.abc import Iterable, Iterator

from greenhouse_protocol.enums import EventSource, EventType, ObservationType
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation

from greenhouse_adapters.wur.agc4_challenge_2024.compartments import GREENHOUSE_ID, Compartment


def spacing_events(
    observations: Iterable[Observation], compartment: Compartment
) -> Iterator[Event]:
    densities = sorted(
        (
            o
            for o in observations
            if o.observation_type == ObservationType.PLANT_DENSITY_PER_M2
            and o.compartment_id == compartment.compartment_id
        ),
        key=lambda o: o.timestamp,
    )
    for before, after in zip(densities, densities[1:], strict=False):
        if after.value == before.value:
            continue
        yield Event(
            event_id=(
                f"wur24_c{compartment.code}_{after.timestamp.strftime('%Y%m%dT%H%M%SZ')}_spacing"
            ),
            greenhouse_id=GREENHOUSE_ID,
            compartment_id=compartment.compartment_id,
            plant_id=None,
            timestamp=after.timestamp,
            event_type=EventType.SPACING,
            # recorded by the compartment's control system, not reported ad hoc
            source=EventSource.CONTROL_SYSTEM,
            parameters={
                "plant_density_before_per_m2": before.value,
                "plant_density_after_per_m2": after.value,
            },
        )
