"""What a scenario's own run's heating delivers as records (P10.3): the heat
its heaters give the house's air each day, as one observation at the day's
end.

The record is the protocol's `HEATING_ENERGY_INCREMENT_MJ_M2`: heat input
over the interval ending at its timestamp, here the run's day, in MJ per
square metre of the house's floor. Its value is modelled, not metered: the
heaters' rated heat output at the levels they ran at, for as long, as the
run's house counts it (`climate.house`), whether a thermostat or commands
ran them. It is the heat given to the air, not the fuel or electricity a
heater draws to give it, which its efficiency would set, and it leaves out
the sun's. Its source is the simulation, by the run's identity, and it names
no sensor: no instrument took it.

A day's increments sum to its total, and the days' to the run's; a consumer
sums them, as it would a meter's. A scenario without a heater has no record
of its heat.
"""

from datetime import datetime, timedelta
from typing import Final

from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.records import observation_id
from greenhouse_sim.services.fields import climate_run
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.world.equipment import Heater

J_PER_MJ: Final = 1e6
# Its value is kept to a kilojoule per square metre.
DECIMALS: Final = 3


def heat_records(scenario_id: str, day: int, start: datetime, run_id: str) -> list[Observation]:
    """The heat a scenario's own run's heaters gave its house's air on its day
    `day`, which starts `day` days after `start`: one record at the day's
    end, or none if it has no heater."""
    config = scenario(scenario_id)
    if not any(isinstance(piece, Heater) for piece in config.layout.equipment):
        return []
    _, climate = climate_run(scenario_id)
    heated_j = climate.house.heated_j(day * DAY_S, (day + 1) * DAY_S)
    floor_m2 = config.envelope.length * config.envelope.width
    at = start + timedelta(seconds=(day + 1) * DAY_S)
    kind = ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2
    return [
        Observation(
            observation_id=observation_id(config.greenhouse_id, at, kind.value),
            greenhouse_id=config.greenhouse_id,
            plant_id=None,
            timestamp=at,
            observation_type=kind,
            value=round(heated_j / J_PER_MJ / floor_m2, DECIMALS),
            source=RecordSource(type=SourceType.SIMULATION, source_id=run_id),
        )
    ]
