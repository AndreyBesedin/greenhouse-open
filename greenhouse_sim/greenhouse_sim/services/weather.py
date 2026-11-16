"""A scenario's weather through a run (P07.1, P07.2): where its site lies,
the weather outside it at a moment of a run, with the wind in the world's
axes and the sun and its light, as a viewer draws them, and the weather
through a day of the run.

A run's moments are seconds from its start (`ScenarioConfig.run_start`), and
lie within a run, as a climate field's do (`greenhouse_sim.services.fields`),
on the run's clock (`greenhouse_sim.core.clock`).
A scenario is asked for under its own weather or a preset's, by name, as
its climate is. A run's weather is digested for an episode's record
(`series_sha256`, P23.2).
"""

import hashlib
import math
from datetime import datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.core.clock import DAY_S, day_start
from greenhouse_sim.scenarios.catalogue import Scenarios
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.runs import checked_moment
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, SceneChanges, changed, scenario
from greenhouse_sim.solar.position import SunPosition, sun_position
from greenhouse_sim.solar.sky import OutsideLight, outside_light
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site

# How often the weather through a day is given, in seconds.
DAY_EVERY_S: Final = 600.0
# How often a run's weather is sampled for its digest (`series_sha256`):
# as often as through a day, so that a season's takes about a second.
SERIES_EVERY_S: Final = DAY_EVERY_S


class WeatherAtAMoment(BaseModel):
    """The weather at a moment of a scenario's run: its site, the moment, as
    an instant and in seconds from the run's start, the weather then, the
    wind's velocity in the world's axes, where the sun stands, with the
    direction towards it in the world's axes (P08.1), and its light and the
    sky's (P08.3)."""

    model_config = ConfigDict(frozen=True)

    site: Site
    moment: datetime
    time_s: float
    weather: WeatherState
    wind_m_s: Vector3
    sun: SunPosition
    sun_direction: Vector3
    light: OutsideLight


class WeatherThroughADay(BaseModel):
    """A scenario's weather through its runs' first day: when the day
    starts, and the weather every `every_s`, at those seconds from its
    start, with where the sun stands and the direction towards it (P08.2),
    for its path across the sky."""

    model_config = ConfigDict(frozen=True)

    start: datetime
    every_s: float
    times_s: list[float]
    weather: list[WeatherState]
    sun: list[SunPosition]
    sun_directions: list[Vector3]


def _under(catalogue: Scenarios, scenario_id: str, weather: str | None) -> ScenarioConfig:
    return changed(
        catalogue,
        scenario(catalogue, scenario_id),
        SceneChanges(weather=weather or DEFAULT_WEATHER),
    )


def at_a_moment(
    catalogue: Scenarios, scenario_id: str, time_s: float = 0.0, weather: str | None = None
) -> WeatherAtAMoment:
    """A scenario's weather `time_s` into a run, under its own weather or a
    preset's. A moment outside a run is refused, as is one its weather does
    not know."""
    config = _under(catalogue, scenario_id, weather)
    checked_moment(config, time_s)
    try:
        state = config.run_weather().at(time_s)
    except ValueError as unknown:
        raise InvalidRequest(str(unknown)) from unknown
    moment = config.run_start() + timedelta(seconds=time_s)
    sun = sun_position(moment, config.site)
    return WeatherAtAMoment(
        site=config.site,
        moment=moment,
        time_s=time_s,
        weather=state,
        wind_m_s=state.wind_m_s(config.site),
        sun=sun,
        sun_direction=sun.direction(config.site),
        light=outside_light(state.global_radiation_w_m2, sun, moment),
    )


def through_the_day(
    catalogue: Scenarios, scenario_id: str, weather: str | None = None, time_s: float = 0.0
) -> WeatherThroughADay:
    """A scenario's weather every `DAY_EVERY_S` through the day of a run that
    `time_s` belongs to (`greenhouse_sim.core.clock`), by default its first,
    under its own weather or a preset's. A moment outside a run is refused,
    as is a weather that does not know the whole day."""
    config = _under(catalogue, scenario_id, weather)
    first = day_start(checked_moment(config, time_s))
    run = config.run_weather()
    times = [first + step * DAY_EVERY_S for step in range(int(DAY_S // DAY_EVERY_S) + 1)]
    try:
        states = [run.at(time) for time in times]
    except ValueError as unknown:
        raise InvalidRequest(str(unknown)) from unknown
    start = config.run_start()
    suns = [sun_position(start + timedelta(seconds=time), config.site) for time in times]
    return WeatherThroughADay(
        start=start,
        every_s=DAY_EVERY_S,
        times_s=times,
        weather=states,
        sun=suns,
        sun_directions=[sun.direction(config.site) for sun in suns],
    )


def series_sha256(
    catalogue: Scenarios,
    scenario_id: str,
    weather: str | None,
    until_s: float,
    every_s: float = SERIES_EVERY_S,
) -> str:
    """The SHA-256 of the weather a scenario's run is under, its seed's mark
    and all, every `every_s` from its start through `until_s`: each state's
    JSON, one line each. Two runs under one weather and seed share it."""
    run = _under(catalogue, scenario_id, weather).run_weather()
    digest = hashlib.sha256()
    for step in range(math.floor(until_s / every_s) + 1):
        digest.update(run.at(step * every_s).model_dump_json().encode() + b"\n")
    return digest.hexdigest()
