"""A scenario's weather through a run (P07.1, P07.2): where its site lies,
the weather outside it at a moment of a run, with the wind in the world's
axes, as a viewer draws it, and the weather through the run's first day.

A run's moments are seconds from its start (`ScenarioConfig.run_start`), and
lie within a run, as a climate field's do (`greenhouse_sim.services.fields`).
A scenario is asked for under its own weather or a preset's, by name, as
its climate is.
"""

from datetime import datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import LONGEST_RUN_S
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, SceneChanges, changed, scenario
from greenhouse_sim.solar.position import SunPosition, sun_position
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site

# A day, and how often the weather through it is given, in seconds.
DAY_S: Final = 86_400.0
DAY_EVERY_S: Final = 600.0


class WeatherAtAMoment(BaseModel):
    """The weather at a moment of a scenario's run: its site, the moment, as
    an instant and in seconds from the run's start, the weather then, the
    wind's velocity in the world's axes, and where the sun stands, with the
    direction towards it in the world's axes (P08.1)."""

    model_config = ConfigDict(frozen=True)

    site: Site
    moment: datetime
    time_s: float
    weather: WeatherState
    wind_m_s: Vector3
    sun: SunPosition
    sun_direction: Vector3


class WeatherThroughADay(BaseModel):
    """A scenario's weather through its runs' first day: when the day
    starts, and the weather every `every_s`, at those seconds from its
    start."""

    model_config = ConfigDict(frozen=True)

    start: datetime
    every_s: float
    times_s: list[float]
    weather: list[WeatherState]


def _under(scenario_id: str, weather: str | None) -> ScenarioConfig:
    return changed(scenario(scenario_id), SceneChanges(weather=weather or DEFAULT_WEATHER))


def at_a_moment(
    scenario_id: str, time_s: float = 0.0, weather: str | None = None
) -> WeatherAtAMoment:
    """A scenario's weather `time_s` into a run, under its own weather or a
    preset's. A moment outside a run is refused, as is one its weather does
    not know."""
    if not 0.0 <= time_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a run lasts from 0 to {LONGEST_RUN_S:g} s, not {time_s:g}")
    config = _under(scenario_id, weather)
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
    )


def through_the_day(scenario_id: str, weather: str | None = None) -> WeatherThroughADay:
    """A scenario's weather every `DAY_EVERY_S` through its runs' first day,
    under its own weather or a preset's. A weather that does not know the
    whole day is refused."""
    config = _under(scenario_id, weather)
    run = config.run_weather()
    times = [step * DAY_EVERY_S for step in range(int(DAY_S // DAY_EVERY_S) + 1)]
    try:
        states = [run.at(time) for time in times]
    except ValueError as unknown:
        raise InvalidRequest(str(unknown)) from unknown
    return WeatherThroughADay(
        start=config.run_start(), every_s=DAY_EVERY_S, times_s=times, weather=states
    )
