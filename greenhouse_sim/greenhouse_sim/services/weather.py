"""A scenario's weather through a run (P07.1): where its site lies, and the
weather outside it at a moment of a run, with the wind in the world's axes,
as a viewer draws it.

A run's moments are seconds from its start (`ScenarioConfig.run_start`), and
lie within a run, as a climate field's do (`greenhouse_sim.services.fields`).
"""

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import LONGEST_RUN_S
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site


class WeatherAtAMoment(BaseModel):
    """The weather at a moment of a scenario's run: its site, the moment, as
    an instant and in seconds from the run's start, the weather then, and
    the wind's velocity in the world's axes."""

    model_config = ConfigDict(frozen=True)

    site: Site
    moment: datetime
    time_s: float
    weather: WeatherState
    wind_m_s: Vector3


def at_a_moment(scenario_id: str, time_s: float = 0.0) -> WeatherAtAMoment:
    """A scenario's weather `time_s` into a run. A moment outside a run is
    refused, as is one its weather does not know."""
    if not 0.0 <= time_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a run lasts from 0 to {LONGEST_RUN_S:g} s, not {time_s:g}")
    config = scenario(scenario_id)
    try:
        state = config.run_weather().at(time_s)
    except ValueError as unknown:
        raise InvalidRequest(str(unknown)) from unknown
    return WeatherAtAMoment(
        site=config.site,
        moment=config.run_start() + timedelta(seconds=time_s),
        time_s=time_s,
        weather=state,
        wind_m_s=state.wind_m_s(config.site),
    )
