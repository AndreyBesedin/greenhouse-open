"""Point sensors reading the air where they stand (P06.2).

A point sensor takes a sample every `cadence_s` of a run, from its start,
of one quantity of the air at its position, as the air's field samples it
there (`EnvironmentField.sample`): a temperature sensor its temperature, a
humidity sensor its relative humidity, a CO2 sensor its CO2, an anemometer
its speed. A quantity the field does not carry, as no model gives PAR yet,
is no reading at all: a gap is an absent record.

Each reading becomes an observation (`greenhouse_protocol.Observation`):
the sensor that took it, the moment it was taken, the moment it was
delivered, and its value. What the air really was there leaves by another
path, for evaluation only (`greenhouse_sim.evaluation.sensor_truth`).
"""

import math
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Final

from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.fields.field import EnvironmentField
from greenhouse_sim.records import observation_id
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.sensors import PointSensor

# What each kind of point sensor reads of a field.
QUANTITIES: Final = {
    SensorKind.TEMPERATURE: AirQuantity.TEMPERATURE,
    SensorKind.HUMIDITY: AirQuantity.HUMIDITY,
    SensorKind.CO2: AirQuantity.CO2,
    SensorKind.AIR_SPEED: AirQuantity.VELOCITY,
}
# What each kind of point sensor reports itself as.
OBSERVATION_TYPES: Final = {
    SensorKind.TEMPERATURE: ObservationType.AIR_TEMPERATURE_C,
    SensorKind.HUMIDITY: ObservationType.RELATIVE_HUMIDITY_PCT,
    SensorKind.CO2: ObservationType.CO2_PPM,
    SensorKind.AIR_SPEED: ObservationType.AIR_SPEED_M_S,
    SensorKind.PAR: ObservationType.PAR_UMOL_M2_S,
}

# The air at a moment of a run, in seconds from its start.
type AirAt = Callable[[float], EnvironmentField]


def reads(sensor: PointSensor, field: EnvironmentField) -> float | None:
    """What the air at a sensor's position is, of the quantity it reads, or
    None if the field does not carry it."""
    quantity = QUANTITIES.get(sensor.kind)
    if quantity is None:
        return None
    value = field.sample(quantity, sensor.position)
    if isinstance(value, Vector3):
        return math.sqrt(value.x**2 + value.y**2 + value.z**2)
    return value


def samples(sensor: PointSensor, until_s: float) -> list[float]:
    """The moments a sensor takes its samples up to `until_s`, in seconds
    from the run's start: every `cadence_s`, from the start."""
    return [index * sensor.cadence_s for index in range(int(until_s // sensor.cadence_s) + 1)]


def observe(
    sensors: Sequence[PointSensor],
    air_at: AirAt,
    until_s: float,
    *,
    start: datetime,
    greenhouse_id: str,
    run_id: str,
) -> list[Observation]:
    """Every reading `sensors` take of the air up to `until_s`, as
    observations, in the order they were delivered."""
    source = RecordSource(type=SourceType.SIMULATION, source_id=run_id)
    observations = []
    for sensor in sensors:
        observation_type = OBSERVATION_TYPES[sensor.kind]
        for moment in samples(sensor, until_s):
            value = reads(sensor, air_at(moment))
            if value is None:
                continue
            taken = start + timedelta(seconds=moment)
            observations.append(
                Observation(
                    observation_id=observation_id(sensor.sensor_id, taken, observation_type.value),
                    greenhouse_id=greenhouse_id,
                    plant_id=None,
                    timestamp=taken,
                    observation_type=observation_type,
                    value=value,
                    source=source,
                    sensor_id=sensor.sensor_id,
                    delivered_at=taken,
                )
            )
    return sorted(observations, key=lambda o: (o.delivered_at or o.timestamp, o.sensor_id or ""))
