"""Point sensors reading the air where they stand (P06.2).

A point sensor takes a sample every `cadence_s` of a run, from its start,
of one quantity of the air at its position, as the air's field samples it
there (`EnvironmentField.sample`): a temperature sensor its temperature, a
humidity sensor its relative humidity, a CO2 sensor its CO2, an anemometer
its speed. A quantity the field does not carry, as no model gives PAR yet,
is no reading at all: a gap is an absent record.

A sensor errs as its configuration says (`Imperfections`, P06.3). Its
sample may drop out, and is then no reading; otherwise the truth there is
given its bias, its drift so far (linear in time since the run's start) and
Gaussian noise, rounded to its quantization step, and held within its
instrument's range, flagged `CLIPPED` where it was held. It is delivered
its latency after it was taken. Each sample's draws are seeded by the
scenario's seed, the sensor's identifier and the sample's index, so a
reading is the same however a run is asked for, two sensors never share
their noise, and adding one changes no other's readings.

Each reading becomes an observation (`greenhouse_protocol.Observation`):
the sensor that took it, the moment it was taken, the moment it was
delivered, its value and its quality. What the air really was there leaves
by another path, for evaluation only
(`greenhouse_sim.evaluation.sensor_truth`).
"""

import math
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Final

from greenhouse_protocol.enums import ObservationQuality, ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.fields.field import EnvironmentField
from greenhouse_sim.records import observation_id
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.sensors import Camera, Imperfections, PointSensor

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

# The range each kind of instrument measures over: a reading beyond it is
# held at its end.
MEASURING_RANGES: Final = {
    SensorKind.TEMPERATURE: (-40.0, 80.0),
    SensorKind.HUMIDITY: (0.0, 100.0),
    SensorKind.CO2: (0.0, 10_000.0),
    SensorKind.AIR_SPEED: (0.0, 30.0),
    SensorKind.PAR: (0.0, 3_000.0),
}
SECONDS_PER_HOUR: Final = 3600.0

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


def samples(sensor: PointSensor | Camera, until_s: float) -> list[float]:
    """The moments a sensor takes its samples, or a camera its frames, up to
    `until_s`, in seconds from the run's start: every `cadence_s`, from the
    start."""
    return [index * sensor.cadence_s for index in range(int(until_s // sensor.cadence_s) + 1)]


def erred(
    sensor: PointSensor, truth: float, moment_s: float, index: int, seed: int
) -> tuple[float, bool] | None:
    """What a sensor reports of `truth` at its `index`th sample, taken
    `moment_s` into the run, and whether it was held at its range's end; or
    None if the sample drops out."""
    imperfections: Imperfections = sensor.imperfections
    rng = seeded_rng(seed, "sensor", sensor.sensor_id, index)
    # Drawn in a fixed order, so that one imperfection's draw never moves
    # another's.
    dropped = rng.uniform() < imperfections.dropout
    noise = rng.normal(0.0, imperfections.noise_sd) if imperfections.noise_sd > 0 else 0.0
    if dropped:
        return None
    value = (
        truth
        + imperfections.bias
        + imperfections.drift_per_hour * moment_s / SECONDS_PER_HOUR
        + noise
    )
    step = imperfections.quantization
    if step > 0:
        # Rounded to the step, and written to its own decimals.
        decimals = len(format(step, "f").rstrip("0").partition(".")[2])
        value = round(round(value / step) * step, decimals)
    low, high = MEASURING_RANGES[sensor.kind]
    held = min(max(value, low), high)
    return held, held != value


def observe(
    sensors: Sequence[PointSensor],
    air_at: AirAt,
    until_s: float,
    *,
    start: datetime,
    greenhouse_id: str,
    run_id: str,
    seed: int = 0,
    clean: bool = False,
) -> list[Observation]:
    """Every reading `sensors` have delivered of the air by `until_s`, as
    observations, in the order they were delivered; as clean sensors would
    have read it, if `clean`."""
    source = RecordSource(type=SourceType.SIMULATION, source_id=run_id)
    observations = []
    for sensor in sensors:
        observation_type = OBSERVATION_TYPES[sensor.kind]
        latency = 0.0 if clean else sensor.imperfections.latency_s
        for index, moment in enumerate(samples(sensor, until_s)):
            if moment + latency > until_s:
                break
            truth = reads(sensor, air_at(moment))
            if truth is None:
                continue
            reported = (truth, False) if clean else erred(sensor, truth, moment, index, seed)
            if reported is None:
                continue
            value, held = reported
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
                    delivered_at=taken + timedelta(seconds=latency),
                    quality=frozenset({ObservationQuality.CLIPPED}) if held else frozenset(),
                )
            )
    return sorted(observations, key=lambda o: (o.delivered_at or o.timestamp, o.sensor_id or ""))
