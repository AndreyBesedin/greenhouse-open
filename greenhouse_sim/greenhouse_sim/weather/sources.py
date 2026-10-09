"""Where a scenario's weather comes from (P07.1): a source gives the weather
at any moment, as an aware instant.

- **Constant** (`ConstantWeather`): one weather for the whole of a run, as a
  scenario's outside was before P07. Its pressure, unless given, is the
  standard atmosphere's at its site's elevation.
- **A series** (`WeatherSeries`): records at moments, interpolated linearly
  in time between them. The wind is interpolated as a vector, so that a wind
  turning from 350° to 10° turns through north, not through south, and
  slackens on the way as the mean of its two vectors does. Before its first
  record and after its last, a series knows nothing, and refuses the moment
  rather than invent it.

A run reads its weather on its own clock, in seconds from its start
(`RunWeather`).
"""

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal, Protocol

from pydantic import PositiveFloat

from greenhouse_sim.weather.state import OutsideConditions, WeatherState
from greenhouse_sim.world.site import Site, bearing

# What the wind's speed and direction are interpolated as, not as themselves.
_WIND: Final = frozenset({"wind_speed_m_s", "wind_direction_deg"})
# Slower than this, an interpolated wind is a calm: what is left of two
# opposite winds is rounding, and has no direction of its own.
CALM_M_S: Final = 1e-9


class WeatherSource(Protocol):
    """Gives the weather at any moment it knows."""

    def at(self, moment: datetime) -> WeatherState: ...


class ConstantWeather(OutsideConditions):
    """One weather for the whole of a run, by default a calm 10 °C at 80%,
    its pressure the standard atmosphere's at its site's elevation unless
    given."""

    kind: Literal["constant"] = "constant"
    barometric_pressure_hpa: PositiveFloat | None = None

    def state(self, site: Site) -> WeatherState:
        """This weather, at `site`."""
        pressure = self.barometric_pressure_hpa
        return WeatherState(
            **self.model_dump(exclude={"kind", "barometric_pressure_hpa"}),
            barometric_pressure_hpa=site.standard_pressure_hpa() if pressure is None else pressure,
        )

    def source(self, site: Site) -> WeatherSource:
        """This weather at every moment, at `site`."""
        return _Constant(self.state(site))


@dataclass(frozen=True)
class _Constant:
    state: WeatherState

    def at(self, moment: datetime) -> WeatherState:
        return self.state


def _blowing(state: WeatherState) -> tuple[float, float]:
    """The wind as a vector, east and north, of the way it blows from."""
    angle = math.radians(state.wind_direction_deg)
    return state.wind_speed_m_s * math.sin(angle), state.wind_speed_m_s * math.cos(angle)


def interpolated(earlier: WeatherState, later: WeatherState, share: float) -> WeatherState:
    """The weather `share` of the way from `earlier` to `later`, each
    quantity linearly, the wind as a vector. A calm on the way keeps the
    earlier wind's direction."""
    values = {
        name: (1.0 - share) * getattr(earlier, name) + share * getattr(later, name)
        for name in WeatherState.model_fields
        if name not in _WIND
    }
    (east_0, north_0), (east_1, north_1) = _blowing(earlier), _blowing(later)
    east = (1.0 - share) * east_0 + share * east_1
    north = (1.0 - share) * north_0 + share * north_1
    speed = math.hypot(east, north)
    if speed < CALM_M_S:
        return WeatherState(
            **values, wind_speed_m_s=0.0, wind_direction_deg=earlier.wind_direction_deg
        )
    return WeatherState(
        **values,
        wind_speed_m_s=speed,
        wind_direction_deg=bearing(math.degrees(math.atan2(east, north))),
    )


class WeatherSeries:
    """Weather recorded at moments, in order, each an aware instant, and
    interpolated between them."""

    def __init__(self, records: Sequence[tuple[datetime, WeatherState]]) -> None:
        if not records:
            raise ValueError("a weather series needs at least one record")
        moments = [moment for moment, _ in records]
        naive = [moment for moment in moments if moment.utcoffset() is None]
        if naive:
            raise ValueError(f"a record's moment has no time zone: {naive[0].isoformat()}")
        for before, after in zip(moments, moments[1:], strict=False):
            if after <= before:
                raise ValueError(
                    f"records are in order of time: {after.isoformat()} follows "
                    f"{before.isoformat()}"
                )
        self._moments = moments
        self._states = [state for _, state in records]

    def at(self, moment: datetime) -> WeatherState:
        """The weather at `moment`: a record's, at its moment, or between the
        records either side of it."""
        first, last = self._moments[0], self._moments[-1]
        if moment.utcoffset() is None:
            raise ValueError(f"a moment has a time zone: {moment.isoformat()}")
        if not first <= moment <= last:
            raise ValueError(
                f"the weather is known from {first.isoformat()} to {last.isoformat()}, "
                f"not at {moment.isoformat()}"
            )
        after = bisect_right(self._moments, moment)
        before = after - 1
        if self._moments[before] == moment:
            return self._states[before]
        start, end = self._moments[before], self._moments[after]
        share = (moment - start) / (end - start)
        return interpolated(self._states[before], self._states[after], share)


@dataclass(frozen=True)
class RunWeather:
    """A weather source on a run's clock, from `start`, an aware instant."""

    source: WeatherSource
    start: datetime

    def at(self, time_s: float) -> WeatherState:
        """The weather `time_s` seconds into the run."""
        return self.source.at(self.start + timedelta(seconds=time_s))
