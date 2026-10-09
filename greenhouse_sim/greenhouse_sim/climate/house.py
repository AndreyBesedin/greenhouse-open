"""The house's air as one well-mixed volume (P07.3): the fidelity ladder's
first rung, which follows a climate run's mean through a day in well under
a second.

It takes what its climate run's grid takes, summed over the house's air
(`climate.run`, `climate.transport`): the air's volume, its exchange with
the outside through the glass and the open doors and vents, U A, U the
glass's in the wind (`climate.glazing`), and the flows the wind and the
stack drive through the openings for its mean air (`climate.openings`),
the heat its equipment adds and the water it takes, and the weather at the
middle of each stretch. Between two moments those hold, so the air is
advanced exactly, as the linear equations they make solve:

- **temperature:** dT/dt = (E (T_out − T) + Q / (ρ c_p)) / V, for the
  exchange E in m³/s and the heat added Q, settling where they balance;
- **water:** dw/dt = (W (w_out − w) − R / ρ) / V, for the air's exchange
  W and the water taken R, never below dry air; what the air would then
  hold beyond saturation condenses, and is counted;
- **CO₂:** exchanged through the doors and vents and the gaps the house
  leaks through, as on the grid, as are its heat and water.

It knows the house's mean, not its gradients: a heater's warm corner loses
more through the glass beside it than the mean would, so the grid run's
mean lies a little below this model's while a heater runs.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.climate.glazing import glazing_u_w_m2k
from greenhouse_sim.climate.openings import opening_flows
from greenhouse_sim.climate.psychrometrics import (
    humidity_ratio_g_kg,
    relative_humidity_pct,
    saturation_ratio_g_kg,
)
from greenhouse_sim.climate.run import KEEP_EVERY_S, ClimateRun
from greenhouse_sim.climate.transport import (
    AIR_DENSITY_KG_M3,
    AIR_HEAT_CAPACITY_J_KG_K,
    GRAMS_PER_KG,
)
from greenhouse_sim.weather.state import WeatherState

# The longest stretch advanced at once, in seconds: the weather is taken at
# the middle of each.
STEP_S: Final = KEEP_EVERY_S


@dataclass(frozen=True)
class HouseAir:
    """The house's air at a moment: its temperature (°C), humidity ratio
    (g/kg) and CO₂ (ppm), with the water it has lost so far to equipment and
    to condensation, in kg."""

    temperature_c: float
    humidity_g_kg: float
    co2_ppm: float
    removed_kg: float = 0.0
    condensed_kg: float = 0.0

    def relative_humidity_pct(self) -> float:
        return float(relative_humidity_pct(self.temperature_c, self.humidity_g_kg))


@dataclass(frozen=True)
class _Steady:
    """What the house exchanges and is given at steady levels: its exchange
    with the outside through the glass, for each W/m²K of U (m³/s), the heat
    added (W) and the water taken (kg/s)."""

    glass_m3_s_per_u: float
    heat_w: float
    water_removed_kg_s: float


def _towards(value: float, settled: float, rate_s: float, duration_s: float) -> float:
    """A quantity relaxing towards `settled` at `rate_s` per second."""
    return settled + (value - settled) * math.exp(-rate_s * duration_s)


class WholeHouse:
    """A climate run's house as one volume of air: its air from the run's
    start, under its schedule and its weather."""

    def __init__(self, run: ClimateRun) -> None:
        self.run = run
        air = ~run.solid
        size = run.grid.cell_size
        self.volume_m3 = float(air.sum()) * size.x * size.y * size.z
        self._air = air
        self._steady: dict[tuple[tuple[str, float], ...], _Steady] = {}
        settings = run.settings
        start = HouseAir(
            temperature_c=settings.start_temperature_c,
            humidity_g_kg=float(
                humidity_ratio_g_kg(settings.start_temperature_c, settings.start_humidity_pct)
            ),
            co2_ppm=settings.start_co2_ppm,
        )
        self._kept: dict[float, HouseAir] = {0.0: start}

    def _held(self, time_s: float) -> _Steady:
        levels = self.run.levels_at(time_s)
        key = tuple(sorted(levels.items()))
        if key not in self._steady:
            terms = self.run.terms_at(time_s)
            transport = self.run.transport_at(time_s, openings={})
            air = self._air
            configured_u = self.run.settings.glazing_u_w_m2k
            glass = float(transport.glass_m3_s()[air].sum())
            self._steady[key] = _Steady(
                glass_m3_s_per_u=glass / configured_u if configured_u > 0 else 0.0,
                heat_w=float(terms.heat_w[air].sum()),
                water_removed_kg_s=float(terms.water_removed_kg_s[air].sum()),
            )
        return self._steady[key]

    def _advance(
        self, air: HouseAir, steady: _Steady, outside: WeatherState, duration_s: float
    ) -> HouseAir:
        volume = self.volume_m3
        heat_per_k = AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K
        warming_c_s = steady.heat_w / (heat_per_k * volume)
        settings = self.run.settings
        u = glazing_u_w_m2k(settings.glazing_u_w_m2k, outside.wind_speed_m_s)
        leaks_m3_s = settings.infiltration_per_s(outside.wind_speed_m_s) * volume
        through = opening_flows([vent.site for vent in self.run.vents], air.temperature_c, outside)
        entering = sum(max(flow.net_m3_s, 0.0) + flow.exchange_m3_s for flow in through)
        venting_m3_s = entering + leaks_m3_s
        exchange = u * steady.glass_m3_s_per_u + venting_m3_s
        if exchange > 0:
            settled = outside.air_temperature_c + steady.heat_w / (heat_per_k * exchange)
            temperature = _towards(air.temperature_c, settled, exchange / volume, duration_s)
        else:
            temperature = air.temperature_c + warming_c_s * duration_s
        air_kg = AIR_DENSITY_KG_M3 * volume
        outside_water = float(
            humidity_ratio_g_kg(outside.air_temperature_c, outside.relative_humidity_pct)
        )
        drying_g_kg_s = steady.water_removed_kg_s * GRAMS_PER_KG / air_kg
        venting_s = venting_m3_s / volume
        if venting_s > 0:
            water = _towards(
                air.humidity_g_kg,
                outside_water - drying_g_kg_s / venting_s,
                venting_s,
                duration_s,
            )
            co2 = _towards(air.co2_ppm, outside.co2_ppm, venting_s, duration_s)
        else:
            water = air.humidity_g_kg - drying_g_kg_s * duration_s
            co2 = air.co2_ppm
        removed_kg = steady.water_removed_kg_s * duration_s
        if water < 0:
            # Equipment dries the air it has, never more.
            removed_kg += water * air_kg / GRAMS_PER_KG
            water = 0.0
        saturated = float(saturation_ratio_g_kg(temperature))
        condensed_kg = max(water - saturated, 0.0) * air_kg / GRAMS_PER_KG
        return HouseAir(
            temperature_c=temperature,
            humidity_g_kg=min(water, saturated),
            co2_ppm=co2,
            removed_kg=air.removed_kg + removed_kg,
            condensed_kg=air.condensed_kg + condensed_kg,
        )

    def air_at(self, time_s: float) -> HouseAir:
        """The house's air at `time_s`, from the latest moment kept before
        it, a stretch at a time, at most `STEP_S` long and ending at each of
        its schedule's changes."""
        if time_s < 0:
            raise ValueError("a climate run starts at 0 s")
        start = max(moment for moment in self._kept if moment <= time_s)
        air = self._kept[start]
        changes = {m for m in self.run.schedule.moments() if start < m <= time_s}
        steps = {
            (math.floor(start / STEP_S) + n) * STEP_S
            for n in range(1, int(time_s // STEP_S) - int(start // STEP_S) + 1)
        }
        now = start
        for until in sorted(changes | steps | {time_s}):
            if until > now:
                outside = self.run.weather.at((now + until) / 2)
                air = self._advance(air, self._held(now), outside, until - now)
                now = until
                if until in steps:
                    self._kept[until] = air
        self._kept[time_s] = air
        return air

    def heat_j(self, air: HouseAir, reference_c: float = 0.0) -> float:
        """The heat its air holds above `reference_c`, in joules."""
        return (
            (air.temperature_c - reference_c)
            * AIR_DENSITY_KG_M3
            * AIR_HEAT_CAPACITY_J_KG_K
            * self.volume_m3
        )

    def water_kg(self, air: HouseAir) -> float:
        """The water its air holds, in kilograms."""
        return air.humidity_g_kg * AIR_DENSITY_KG_M3 * self.volume_m3 / GRAMS_PER_KG


def grid_mean(run: ClimateRun, time_s: float) -> HouseAir:
    """A climate run's air at `time_s`, its grid's air averaged as the whole
    house holds it: its mean temperature, humidity ratio and CO₂."""
    air = ~run.solid
    state = run.air_at(time_s)
    return HouseAir(
        temperature_c=float(np.mean(state.temperature[air])),
        humidity_g_kg=float(np.mean(state.humidity[air])),
        co2_ppm=float(np.mean(state.co2[air])),
        removed_kg=state.removed_kg,
        condensed_kg=state.condensed_kg,
    )


class HouseSeries(BaseModel):
    """The house's air at each moment of a trace: its temperature (°C),
    relative humidity (%) and CO₂ (ppm), and the water it has lost to
    equipment and to condensation so far (kg)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature_c: list[float]
    humidity_pct: list[float]
    co2_ppm: list[float]
    removed_kg: list[float]
    condensed_kg: list[float]


class HouseTrace(BaseModel):
    """The house's air through a climate run, and through the same run with
    everything off, at each of its moments, in seconds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    times_s: list[float]
    controlled: HouseSeries
    all_off: HouseSeries


def _series(house: WholeHouse, times_s: Sequence[float]) -> HouseSeries:
    airs = [house.air_at(time) for time in times_s]
    return HouseSeries(
        temperature_c=[air.temperature_c for air in airs],
        humidity_pct=[air.relative_humidity_pct() for air in airs],
        co2_ppm=[air.co2_ppm for air in airs],
        removed_kg=[air.removed_kg for air in airs],
        condensed_kg=[air.condensed_kg for air in airs],
    )


def house_trace(
    run: WholeHouse, everything_off: WholeHouse, times_s: Sequence[float]
) -> HouseTrace:
    """The house's air through `run` and through `everything_off` at each of
    `times_s`."""
    return HouseTrace(
        times_s=list(times_s),
        controlled=_series(run, times_s),
        all_off=_series(everything_off, times_s),
    )
