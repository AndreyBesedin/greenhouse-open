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

from collections.abc import Mapping, Sequence
from datetime import datetime

from greenhouse_protocol.media import CameraFrame
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.evaluation.sensor_truth import SensorTruth, sensor_truth
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.sensors.air import WeatherAt, observe, reads
from greenhouse_sim.sensors.log import SensorFreshness, frames, freshness
from greenhouse_sim.services.fields import Commanded, air_through_a_run
from greenhouse_sim.services.runs import checked_window
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, SceneChanges, changed, scenario
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


def _weather_at(scenario_id: str, weather: str | None) -> WeatherAt:
    """The weather a scenario's run is under, on its clock: its own, or a
    preset's."""
    config = changed(scenario(scenario_id), SceneChanges(weather=weather or DEFAULT_WEATHER))
    return config.run_weather().at


def observations(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    until_s: float = 0.0,
    clean: bool = False,
    weather: str | None = None,
    daily: Sequence[Commanded] | None = None,
    from_s: float | None = None,
) -> SensorObservations:
    """A run's observation log from `from_s`, by default the start of the
    day `until_s` belongs to (`services.runs`), to `until_s`; as clean
    sensors would have made it, if `clean`, for QA. Each sensor's freshness
    is its own at `until_s`, whatever it delivered before the log begins."""
    first = checked_window(scenario(scenario_id), from_s, until_s)
    name = layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(
        scenario_id, name, levels, openings, commands, weather, daily
    )
    weather_at = _weather_at(scenario_id, weather)
    start = run_start(scenario_id)
    greenhouse_id = scenario(scenario_id).greenhouse_id
    point_sensors = _point_sensors(scenario_id, name)
    observed = observe(
        point_sensors,
        air_at,
        until_s,
        start=start,
        greenhouse_id=greenhouse_id,
        run_id=run_id,
        seed=scenario(scenario_id).random_seed,
        clean=clean,
        weather_at=weather_at,
        from_s=first,
    )
    # A quantity the run's air and weather do not give, they never give.
    unavailable = {
        s.sensor_id for s in point_sensors if reads(s, air_at(0.0), weather_at(0.0)) is None
    }
    return SensorObservations(
        run_id=run_id,
        start=start,
        observations=observed,
        freshness=freshness(
            point_sensors,
            until_s,
            start=start,
            seed=scenario(scenario_id).random_seed,
            unavailable=unavailable,
            clean=clean,
        ),
        frames=frames(
            _cameras(scenario_id, name),
            until_s,
            start=start,
            greenhouse_id=greenhouse_id,
            run_id=run_id,
            from_s=first,
        ),
    )


def truth(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    until_s: float = 0.0,
    weather: str | None = None,
    daily: Sequence[Commanded] | None = None,
    from_s: float | None = None,
) -> SensorTruths:
    """What a scenario's point sensors truly sampled from `from_s`, by
    default the start of the day `until_s` belongs to, to `until_s` of a
    run: for evaluation and QA only."""
    first = checked_window(scenario(scenario_id), from_s, until_s)
    name = layout or DEFAULT_LAYOUT
    air_at, run_id = air_through_a_run(
        scenario_id, name, levels, openings, commands, weather, daily
    )
    return SensorTruths(
        run_id=run_id,
        sensors=sensor_truth(
            _point_sensors(scenario_id, name),
            air_at,
            until_s,
            _weather_at(scenario_id, weather),
            from_s=first,
        ),
    )
