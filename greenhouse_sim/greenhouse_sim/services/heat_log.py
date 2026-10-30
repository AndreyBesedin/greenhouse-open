"""What a scenario's own run's heating delivers as records (P10.3): the heat
its heaters give the house's air each hour, as one observation at the
hour's end.

The record is the protocol's `HEATING_ENERGY_INCREMENT_MJ_M2`: heat input
over the interval ending at its timestamp, here an hour of the run, in MJ
per square metre of the house's floor. An hour at a time, a consumer sees
the heater run through the night and stop in the day, as a pipe's
temperature would show it; the reference greenhouse's heater warms the air
directly, and has no pipe whose temperature to record.

Its value is modelled, not metered: the heaters' rated heat output at the
levels they ran at, for as long, as the run's house counts it
(`climate.house`), whether a thermostat or commands ran them. It is the
heat given to the air, not the fuel or electricity a heater draws to give
it, which its efficiency would set, and it leaves out the sun's. Its source
is the simulation, by the run's identity, and it names no sensor: no
instrument took it.

A day's increments sum to its total, the last at its end, and the days' to
the run's; a consumer sums them, as it would a meter's. A scenario without
a heater has no record of its heat.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final

from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.records import observation_id
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.world.capabilities import Heats
from greenhouse_sim.world.equipment import can

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

J_PER_MJ: Final = 1e6
# Its value is kept to a kilojoule per square metre.
DECIMALS: Final = 3
# How long each record's interval is, in seconds: an hour.
EVERY_S: Final = HOUR_S


def heats(config: ScenarioConfig) -> bool:
    """Whether a scenario's run has a heater, whose heat it logs."""
    return any(can(piece, Heats) for piece in config.layout.equipment)


def heat_records(
    simulator: Simulator, run: RunRequest, day: int, start: datetime, run_id: str
) -> list[Observation]:
    """The heat a run's heaters gave its house's air on its day `day`, which
    starts `day` days after `start`, such as a scenario's own run with a
    layout rearranged or targets changed, each named by `run_id`: a record
    at the end of each of its hours, or none if it has no heater."""
    config = scenario(simulator.catalogue, run.scenario_id)
    if not heats(config):
        return []
    _, climate = climate_run(simulator, run)
    floor_m2 = config.envelope.length * config.envelope.width
    kind = ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2
    source = RecordSource(type=SourceType.SIMULATION, source_id=run_id)
    hours = range(round(DAY_S / EVERY_S))
    records = []
    for hour in hours:
        until_s = day * DAY_S + (hour + 1) * EVERY_S
        heated_j = climate.house.heated_j(until_s - EVERY_S, until_s)
        at = start + timedelta(seconds=until_s)
        records.append(
            Observation(
                observation_id=observation_id(config.greenhouse_id, at, kind.value),
                greenhouse_id=config.greenhouse_id,
                plant_id=None,
                timestamp=at,
                observation_type=kind,
                value=round(heated_j / J_PER_MJ / floor_m2, DECIMALS),
                source=source,
            )
        )
    return records
