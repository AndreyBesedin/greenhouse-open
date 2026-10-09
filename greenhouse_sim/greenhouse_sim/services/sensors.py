"""A scenario's sensors through a run (P06.2): what they observe, on the
normal path, with each one's freshness and its cameras' frames (P06.6),
and, for evaluation and QA only, what was truly there.

A run's moments are seconds from its start, which is its scenario's start
date at midnight at its site (P07.1), until the crop's days and the air's
seconds share a clock (P09). The run is asked for as its climate field is
(`greenhouse_sim.services.fields`), and refused as it is.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime

from greenhouse_protocol.media import CameraFrame
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.evaluation.sensor_truth import SensorTruth, sensor_truth
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.sensors.air import observe, reads
from greenhouse_sim.sensors.log import SensorFreshness, frames, freshness
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import LONGEST_RUN_S, Commanded, air_through_a_run
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario
from greenhouse_sim.world.sensors import Camera, PointSensor


class SensorObservations(BaseModel):
    """A run's observation log up to a moment: what its point sensors
    observed, in the order delivered, whether each is fresh, and the frames
    its cameras took; the run that produced them, and when it started."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    start: datetime
    observations: list[Observation]
    freshness: list[SensorFreshness]
    frames: list[CameraFrame]


class SensorTruths(BaseModel):
    """What each of a scenario's point sensors truly sampled up to a moment
    of a run: for evaluation and QA only."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    sensors: list[SensorTruth]


def run_start(scenario_id: str) -> datetime:
    """The instant a scenario's runs start: its start date's midnight at its
    site."""
    return scenario(scenario_id).run_start()


def _point_sensors(scenario_id: str, layout: str) -> list[PointSensor]:
    config = changed(scenario(scenario_id), SceneChanges(layout=layout))
    return [sensor for sensor in config.layout.sensors if isinstance(sensor, PointSensor)]


def _cameras(scenario_id: str, layout: str) -> list[Camera]:
    config = changed(scenario(scenario_id), SceneChanges(layout=layout))
    return [sensor for sensor in config.layout.sensors if isinstance(sensor, Camera)]


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
    clean: bool = False,
) -> SensorObservations:
    """A run's observation log up to `until_s`; as clean sensors would have
    made it, if `clean`, for QA."""
    until = _checked_until(until_s)
    name = layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(scenario_id, name, levels, openings, commands)
    start = run_start(scenario_id)
    greenhouse_id = scenario(scenario_id).greenhouse_id
    point_sensors = _point_sensors(scenario_id, name)
    observed = observe(
        point_sensors,
        air_at,
        until,
        start=start,
        greenhouse_id=greenhouse_id,
        run_id=run_id,
        seed=scenario(scenario_id).random_seed,
        clean=clean,
    )
    # A quantity the run's air does not give, it never gives.
    unavailable = {s.sensor_id for s in point_sensors if reads(s, air_at(0.0)) is None}
    return SensorObservations(
        run_id=run_id,
        start=start,
        observations=observed,
        freshness=freshness(
            point_sensors, observed, until, start=start, unavailable=unavailable, clean=clean
        ),
        frames=frames(
            _cameras(scenario_id, name),
            until,
            start=start,
            greenhouse_id=greenhouse_id,
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
