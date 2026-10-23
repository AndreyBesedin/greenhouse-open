"""A scenario's sensors through a run (P06.2): what they observe, on the
normal path, with each one's freshness and its cameras' frames (P06.6),
and, for evaluation and QA only, what was truly there. A weather station
reads the weather the run is under (P07.2).

A run's moments are seconds from its start, which is its scenario's start
date at midnight at its site (P07.1), through its scenario's days, on the
run's clock (`greenhouse_sim.core.clock`, P09.2). A log is a day's unless a
longer one is asked for. The run is asked for as its climate field is
(`greenhouse_sim.services.fields`), and refused as it is.
"""

import threading
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from greenhouse_protocol.media import CameraFrame
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.evaluation.sensor_truth import SensorTruth, sensor_truth
from greenhouse_sim.fields.field import EnvironmentField
from greenhouse_sim.scenarios.catalogue import Scenarios
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.sensors.air import AirAt, WeatherAt, observe, reads, samples
from greenhouse_sim.sensors.log import SensorFreshness, frames, freshness
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest, checked_window
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, SceneChanges, changed, scenario
from greenhouse_sim.world.sensors import Camera, PointSensor

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator


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


class CameraAt(BaseModel):
    """Where a camera stands with its frames at a moment of a run: how many
    it has taken since the run's start, and its latest, if any."""

    model_config = ConfigDict(frozen=True)

    sensor_id: str
    frames: int
    latest: CameraFrame | None


class SensorsAt(BaseModel):
    """Where a run's sensors stand at a moment, as its observation log would
    say, without the log: each point sensor's freshness, and each camera's
    frames; the run that produced them, and when it started."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    start: datetime
    freshness: list[SensorFreshness]
    cameras: list[CameraAt]


class SensorTruths(BaseModel):
    """What each of a scenario's point sensors truly sampled up to a moment
    of a run: for evaluation and QA only."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    sensors: list[SensorTruth]


def run_start(catalogue: Scenarios, scenario_id: str) -> datetime:
    """The instant a scenario's runs start: its start date's midnight at its
    site."""
    return scenario(catalogue, scenario_id).run_start()


def _point_sensors(catalogue: Scenarios, scenario_id: str, layout: str) -> list[PointSensor]:
    config = changed(catalogue, scenario(catalogue, scenario_id), SceneChanges(layout=layout))
    return [sensor for sensor in config.layout.sensors if isinstance(sensor, PointSensor)]


def _cameras(catalogue: Scenarios, scenario_id: str, layout: str) -> list[Camera]:
    config = changed(catalogue, scenario(catalogue, scenario_id), SceneChanges(layout=layout))
    return [sensor for sensor in config.layout.sensors if isinstance(sensor, Camera)]


def _weather_at(catalogue: Scenarios, scenario_id: str, weather: str | None) -> WeatherAt:
    """The weather a scenario's run is under, on its clock: its own, or a
    preset's."""
    config = changed(
        catalogue,
        scenario(catalogue, scenario_id),
        SceneChanges(weather=weather or DEFAULT_WEATHER),
    )
    return config.run_weather().at


def observations(
    simulator: Simulator,
    run: RunRequest,
    until_s: float = 0.0,
    clean: bool = False,
    from_s: float | None = None,
) -> SensorObservations:
    """A run's observation log from `from_s`, by default the start of the
    day `until_s` belongs to (`services.runs`), to `until_s`; as clean
    sensors would have made it, if `clean`, for QA. Each sensor's freshness
    is its own at `until_s`, whatever it delivered before the log begins."""
    scenario_id = run.scenario_id
    first = checked_window(scenario(simulator.catalogue, scenario_id), from_s, until_s)
    name = run.layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(simulator, run)
    weather_at = _weather_at(simulator.catalogue, scenario_id, run.weather)
    start = run_start(simulator.catalogue, scenario_id)
    greenhouse_id = scenario(simulator.catalogue, scenario_id).greenhouse_id
    point_sensors = _point_sensors(simulator.catalogue, scenario_id, name)
    observed = observe(
        point_sensors,
        air_at,
        until_s,
        start=start,
        greenhouse_id=greenhouse_id,
        run_id=run_id,
        seed=scenario(simulator.catalogue, scenario_id).random_seed,
        clean=clean,
        weather_at=weather_at,
        from_s=first,
    )
    return SensorObservations(
        run_id=run_id,
        start=start,
        observations=observed,
        freshness=_freshness(
            simulator.catalogue, scenario_id, point_sensors, air_at, weather_at, until_s, clean
        ),
        frames=frames(
            _cameras(simulator.catalogue, scenario_id, name),
            until_s,
            start=start,
            greenhouse_id=greenhouse_id,
            run_id=run_id,
            from_s=first,
        ),
    )


class Stopped(Exception):
    """Readings no longer wanted: the work asking for them was stopped."""


def delivered_between(
    simulator: Simulator,
    run: RunRequest,
    after_s: float | None,
    until_s: float,
    every_s: float | None = None,
    named: str | None = None,
    stop: threading.Event | None = None,
) -> tuple[list[Observation], str]:
    """What a run delivered of its point sensors' readings after `after_s`
    and by `until_s`, from the run's start if `after_s` is None, in the order
    delivered, taken every `every_s` (all if None); with the run's identity.
    The run is such as a scenario's own, with a layout rearranged or targets
    changed. Each reading is named by `named`, by default the run's
    identity: a playback names those of a run whose targets it changed by
    its epoch's run (decision 0043). Spans that meet end to end deliver each
    reading once, a late one in the span it arrived in. Once `stop` is set,
    no other moment's air is worked out: `Stopped` is raised instead, so
    that a playback stopped does not finish the day it was working out."""
    scenario_id = run.scenario_id
    config = scenario(simulator.catalogue, scenario_id)
    point_sensors = _point_sensors(simulator.catalogue, scenario_id, run.layout or DEFAULT_LAYOUT)
    air_at, run_id = air_through_a_run(simulator, run)
    if stop is not None:
        air_at = _until_stopped(air_at, stop)
    start = run_start(simulator.catalogue, scenario_id)
    latest = max((sensor.imperfections.latency_s for sensor in point_sensors), default=0.0)
    observed = observe(
        point_sensors,
        air_at,
        until_s,
        start=start,
        greenhouse_id=config.greenhouse_id,
        run_id=named or run_id,
        seed=config.random_seed,
        weather_at=_weather_at(simulator.catalogue, scenario_id, run.weather),
        from_s=0.0 if after_s is None else max(0.0, after_s - latest),
        every_s=every_s,
    )
    if after_s is None:
        return observed, run_id
    after = start + timedelta(seconds=after_s)
    return [o for o in observed if (o.delivered_at or o.timestamp) > after], run_id


def _until_stopped(air_at: AirAt, stop: threading.Event) -> AirAt:
    """`air_at`, raising `Stopped` once `stop` is set rather than working
    another moment out."""

    def checked(moment_s: float) -> EnvironmentField:
        if stop.is_set():
            raise Stopped("stopped before the moment's air was worked out")
        return air_at(moment_s)

    return checked


def sensors_at(simulator: Simulator, run: RunRequest, until_s: float = 0.0) -> SensorsAt:
    """Where a run's sensors stand at `until_s`: each point sensor's
    freshness, as its observation log gives it, and each camera's frames,
    working out none of the log's observations, which sample the house's air
    every minute. Asked for as the log is, and refused as it is."""
    scenario_id = run.scenario_id
    checked_window(scenario(simulator.catalogue, scenario_id), None, until_s)
    name = run.layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(simulator, run)
    start = run_start(simulator.catalogue, scenario_id)
    greenhouse_id = scenario(simulator.catalogue, scenario_id).greenhouse_id
    cameras = []
    for camera in _cameras(simulator.catalogue, scenario_id, name):
        taken = samples(camera, until_s)
        latest = frames(
            [camera],
            until_s,
            start=start,
            greenhouse_id=greenhouse_id,
            run_id=run_id,
            from_s=taken[-1] if taken else until_s,
        )
        cameras.append(
            CameraAt(sensor_id=camera.sensor_id, frames=len(taken), latest=next(iter(latest), None))
        )
    return SensorsAt(
        run_id=run_id,
        start=start,
        freshness=_freshness(
            simulator.catalogue,
            scenario_id,
            _point_sensors(simulator.catalogue, scenario_id, name),
            air_at,
            _weather_at(simulator.catalogue, scenario_id, run.weather),
            until_s,
        ),
        cameras=cameras,
    )


def _freshness(
    catalogue: Scenarios,
    scenario_id: str,
    point_sensors: Sequence[PointSensor],
    air_at: AirAt,
    weather_at: WeatherAt,
    until_s: float,
    clean: bool = False,
) -> list[SensorFreshness]:
    """Each point sensor's freshness at `until_s`; a quantity the run's air
    and weather do not give, they never give."""
    unavailable = {
        s.sensor_id for s in point_sensors if reads(s, air_at(0.0), weather_at(0.0)) is None
    }
    return freshness(
        point_sensors,
        until_s,
        start=run_start(catalogue, scenario_id),
        seed=scenario(catalogue, scenario_id).random_seed,
        unavailable=unavailable,
        clean=clean,
    )


def truth(
    simulator: Simulator, run: RunRequest, until_s: float = 0.0, from_s: float | None = None
) -> SensorTruths:
    """What a run's point sensors truly sampled from `from_s`, by default
    the start of the day `until_s` belongs to, to `until_s`: for evaluation
    and QA only."""
    scenario_id = run.scenario_id
    first = checked_window(scenario(simulator.catalogue, scenario_id), from_s, until_s)
    name = run.layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(simulator, run)
    return SensorTruths(
        run_id=run_id,
        sensors=sensor_truth(
            _point_sensors(simulator.catalogue, scenario_id, name),
            air_at,
            until_s,
            _weather_at(simulator.catalogue, scenario_id, run.weather),
            from_s=first,
        ),
    )
