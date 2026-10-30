"""A run's capability and goal context (P15.2, decision 0061): what a
principal may read and do in one epoch of a scenario's run, as a policy's
port gives it (`greenhouse_protocol.context`). It is built from the run's
installation as the run plays it, its scenario and its authorisation, and
says nothing of how the simulated world works:

- **its observation sources:**
  - each point sensor, its reading's type, as often as a consumer
    receives it: every sample the sensor takes at a multiple of the
    consumer's cadence;
  - the heat meter, hourly, when the run has a heater (`heat_log`);
  - the crop walk, a measurement model's, daily, when the run grows
    plants (`crop_log`).

  Not a camera, whose frames are not observations. Not a sensor's noise,
  drift or faults, nor its position, which are the simulated world's;
- **its devices:** each piece of equipment, by what it does, and each door
  and vent, which opens, each at a level from 0 to 1. None hands back to
  its loop (`auto`), which the run does not do yet;
- **its targets,** with a heating loop: by day and by night, in °C, from
  the setpoints' range's foot to the highest that keeps the controller's
  dead band (`climate_runs.most_heating_c`). The target in force is not
  observed yet;
- **its crop:** an instance on each row of its crop rows
  (`world.scopes`), grown by plant, with its plants as a consumer is told
  of them and the crop actions its model takes;
- **when it carries each kind of action out,** where not at any instant:
  a target on the minute, crop work at the start of each day after the
  first (`gateway.RunExecutor`);
- **its gateway's limits** and **the principal's grants;**
- **no goals,** which an experiment's scenario fixes (P15, stage B).
"""

import math
from fractions import Fraction
from typing import Final

from greenhouse_protocol.actions import ActionKind
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.context import (
    ActionCadence,
    CapabilityContext,
    CropBasis,
    CropInstance,
    DeviceControl,
    ObservationSource,
    ObservedQuantity,
    SourceKind,
    TargetControl,
)
from greenhouse_protocol.contracts.gateway import GatewayLimits
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.plan import Principal

from greenhouse_sim.climate.commands import TARGET_EVERY_S
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.equipment import Target
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.sensors.air import OBSERVATION_TYPES
from greenhouse_sim.services import heat_log
from greenhouse_sim.services.climate_runs import SETPOINT_RANGE_C, most_heating_c
from greenhouse_sim.services.crop_log import WALKED
from greenhouse_sim.services.crop_models import registration
from greenhouse_sim.services.gateway import run_kinds
from greenhouse_sim.services.runs import CROP_KINDS
from greenhouse_sim.services.scenarios import described_plants
from greenhouse_sim.world.scopes import row_scopes, scope_plants
from greenhouse_sim.world.sensors import PointSensor

# The sources that name no sensor in their records, as the context names
# them: with a ':', which no sensor's identifier holds (`ITEM_ID_PATTERN`),
# so that none is a sensor's too.
HEAT_METER: Final = "meter:heating"
CROP_WALK: Final = "measurement:crop_walk"
# What a door or a vent does, at a level: it opens.
OPENS: Final = "opens"
CELSIUS: Final = "°C"


def run_context(
    config: ScenarioConfig,
    *,
    run_id: str,
    epoch: int,
    principal: Principal,
    authorisation: AuthorisationConfig,
    limits: GatewayLimits,
    every_s: float,
) -> CapabilityContext:
    """The context of `principal` in epoch `epoch` of the run `run_id` of
    `config`, as the run plays it, its readings received every `every_s`:
    see the module."""
    return CapabilityContext(
        run_id=run_id,
        epoch=epoch,
        greenhouse_id=config.greenhouse_id,
        principal=principal,
        sources=_sources(config, every_s),
        devices=_devices(config),
        targets=_targets(config),
        crops=_crops(config),
        cadences=_cadences(config),
        limits=limits,
        grants=tuple(authorisation.grants_of(principal)),
    )


def delivered_every_s(cadence_s: float, every_s: float) -> float:
    """How often a sensor that samples every `cadence_s` reaches a consumer
    that receives the samples taken at multiples of `every_s`: the least
    common multiple of the two, each the decimal it is written as, 1.2 s
    for 1.2 rather than the binary fraction nearest it."""
    sampled, received = Fraction(str(cadence_s)), Fraction(str(every_s))
    return float(
        Fraction(
            math.lcm(sampled.numerator, received.numerator),
            math.gcd(sampled.denominator, received.denominator),
        )
    )


def _sources(config: ScenarioConfig, every_s: float) -> tuple[ObservationSource, ...]:
    sensors = [
        ObservationSource(
            source_id=sensor.sensor_id,
            kind=SourceKind.SENSOR,
            quantities=(
                ObservedQuantity(
                    observation_type=OBSERVATION_TYPES[sensor.kind],
                    every_s=delivered_every_s(sensor.cadence_s, every_s),
                ),
            ),
        )
        for sensor in config.layout.sensors
        if isinstance(sensor, PointSensor)
    ]
    meter = ObservationSource(
        source_id=HEAT_METER,
        kind=SourceKind.METER,
        quantities=(
            ObservedQuantity(
                observation_type=ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2,
                every_s=heat_log.EVERY_S,
            ),
        ),
    )
    walk = ObservationSource(
        source_id=CROP_WALK,
        kind=SourceKind.MEASUREMENT,
        quantities=tuple(ObservedQuantity(observation_type=kind, every_s=DAY_S) for kind in WALKED),
    )
    return (
        *sensors,
        *([meter] if heat_log.heats(config) else []),
        *([walk] if described_plants(config) else []),
    )


def _devices(config: ScenarioConfig) -> tuple[DeviceControl, ...]:
    equipment = [
        DeviceControl(
            device_id=piece.actuator_id,
            does=frozenset(capability.name for capability in piece.capabilities()),
        )
        for piece in config.layout.equipment
    ]
    openings = [
        DeviceControl(device_id=opening.opening_id, does=frozenset({OPENS}))
        for opening in config.envelope.openings
    ]
    return (*equipment, *openings)


def _targets(config: ScenarioConfig) -> tuple[TargetControl, ...]:
    if config.thermostat is None:
        return ()
    low, high = SETPOINT_RANGE_C
    targets = []
    for target in Target:
        most_c = most_heating_c(config, target)
        targets.append(
            TargetControl(
                target=target,
                unit=CELSIUS,
                low=low,
                high=high if most_c is None else min(high, most_c),
            )
        )
    return tuple(targets)


def _crops(config: ScenarioConfig) -> tuple[CropInstance, ...]:
    taken = registration(config).crop_actions
    plants = {plant.plant_id: plant for plant in described_plants(config)}
    scopes = row_scopes(config.layout, config.envelope)
    held = scope_plants(scopes, list(plants))
    return tuple(
        CropInstance(
            scope_id=scope.scope_id,
            scope_kind=scope.kind,
            grown_by=CropBasis.PLANT,
            cultivated_m2=scope.cultivated_m2,
            floor_m2=scope.floor_m2,
            plants=tuple(plants[plant_id] for plant_id in held[scope.scope_id]),
            crop_actions=frozenset() if taken is None else taken.kinds,
        )
        for scope in scopes
    )


def _cadences(config: ScenarioConfig) -> tuple[ActionCadence, ...]:
    kinds = run_kinds(config)
    targets = (
        [ActionCadence(kind=ActionKind.SET_TARGET, every_s=TARGET_EVERY_S)]
        if ActionKind.SET_TARGET in kinds
        else []
    )
    crop_work = [
        ActionCadence(kind=kind, every_s=DAY_S, first_s=DAY_S)
        for kind in sorted(kinds & CROP_KINDS)
    ]
    return (*targets, *crop_work)
