"""A scenario's sensors through a run (P06.2): what they observe, on the
normal path, and, for evaluation and QA only, what was truly there.

A run's moments are seconds from its start, which is its scenario's start
date at midnight, UTC, until the crop's days and the air's seconds share a
clock (P09). The run is asked for as its climate field is
(`greenhouse_sim.services.fields`), and refused as it is.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time

from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.evaluation.sensor_truth import SensorTruth, sensor_truth
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.sensors.air import observe
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import LONGEST_RUN_S, Commanded, air_through_a_run
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario
from greenhouse_sim.world.sensors import PointSensor


class SensorObservations(BaseModel):
    """What a scenario's point sensors observed up to a moment of a run, in
    the order delivered, and the run that produced them."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    observations: list[Observation]


class SensorTruths(BaseModel):
    """What each of a scenario's point sensors truly sampled up to a moment
    of a run: for evaluation and QA only."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    sensors: list[SensorTruth]


def run_start(scenario_id: str) -> datetime:
    """The instant a scenario's runs start: its start date's midnight, UTC."""
    return datetime.combine(scenario(scenario_id).start_date, time(0), tzinfo=UTC)


def _point_sensors(scenario_id: str, layout: str) -> list[PointSensor]:
    config = changed(scenario(scenario_id), SceneChanges(layout=layout))
    return [sensor for sensor in config.layout.sensors if isinstance(sensor, PointSensor)]


def _checked_until(until_s: float) -> float:
    if not 0.0 <= until_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a run lasts from 0 to {LONGEST_RUN_S:g} s, not {until_s:g}")
    return until_s


def observations(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    until_s: float = 0.0,
) -> SensorObservations:
    """What a scenario's point sensors observed up to `until_s` of a run."""
    until = _checked_until(until_s)
    name = layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(scenario_id, name, levels, openings, commands)
    return SensorObservations(
        run_id=run_id,
        observations=observe(
            _point_sensors(scenario_id, name),
            air_at,
            until,
            start=run_start(scenario_id),
            greenhouse_id=scenario(scenario_id).greenhouse_id,
            run_id=run_id,
        ),
    )


def truth(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    until_s: float = 0.0,
) -> SensorTruths:
    """What a scenario's point sensors truly sampled up to `until_s` of a
    run: for evaluation and QA only."""
    until = _checked_until(until_s)
    name = layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(scenario_id, name, levels, openings, commands)
    return SensorTruths(
        run_id=run_id,
        sensors=sensor_truth(_point_sensors(scenario_id, name), air_at, until),
    )
