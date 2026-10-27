"""The house's air as one well-mixed volume (P07.3): the fidelity ladder's
first rung, which follows a climate run's mean through a day in well under
a second.

It takes what its climate run's grid takes, summed over the house's air
(`climate.run`, `climate.transport`): the air's volume, its exchange with
the outside through the glass and the open doors and vents, U A, U the
glass's in the wind (`climate.glazing`), and the flows the wind and the
stack drive through the openings for its mean air (`climate.openings`),
the heat its equipment and the sun add (P08.8) and the water it takes, and
the weather at the middle of each stretch. Between two moments those hold, so the air is
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

A house takes over another's air up to the first moment their schedules
differ, as a grid run does (`carry_on_from`), and averages its air over a
stretch of its run, such as a day the crop lives in it (`mean_between`).
"""

import math
import threading
import weakref
from bisect import bisect_right, insort
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

import numpy as np
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.climate.control import DehumidifyingLoop, VentingLoop
from greenhouse_sim.climate.glazing import glazing_u_w_m2k
from greenhouse_sim.climate.openings import opening_flows
from greenhouse_sim.climate.psychrometrics import (
    humidity_ratio_g_kg,
    relative_humidity_pct,
    saturation_ratio_g_kg,
)
from greenhouse_sim.climate.run import KEEP_EVERY_S, LOOK_AGAIN_S, ClimateRun
from greenhouse_sim.climate.thermostat import OFF, ON
from greenhouse_sim.climate.transport import (
    AIR_HEAT_CAPACITY_J_KG_K,
    GRAMS_PER_KG,
)
from greenhouse_sim.units import AIR_DENSITY_KG_M3
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.capabilities import Heats

# The longest stretch advanced at once, in seconds: the weather is taken at
# the middle of each.
STEP_S: Final = KEEP_EVERY_S
# How a relative humidity's edge is found through a stretch: bracketed by
# moments so many to each of its quicker exponential's time constants, from
# so few to so many in a stretch, then halved to so many seconds.
SAMPLES_A_RATE: Final = 8
FEWEST_SAMPLES: Final = 16
MOST_SAMPLES: Final = 1024
HUMIDITY_EDGE_S: Final = 1e-9


@dataclass(frozen=True, slots=True)
class HouseAir:
    """The house's air at a moment: its temperature (°C), humidity ratio
    (g/kg) and CO₂ (ppm), with the water it has lost so far to equipment and
    to condensation, in kg; the heat its heaters have given it so far, in J;
    and how its controller's loops stood up to then (`climate.control`):
    whether its thermostat ran its heater (`climate.thermostat`), how many
    of its vents' stages stood open, whether its dehumidifying loop ran its
    dehumidifier, and whether it held the air outside drier enough to vent
    into (P11.2). The loops' state is kept
    here, with the air it was decided from, not as the controller's model's
    state (decision 0055): a checkpoint keeps the house's air at two
    moments, its day's start and an hour before, and each carries how the
    loops stood then."""

    temperature_c: float
    humidity_g_kg: float
    co2_ppm: float
    removed_kg: float = 0.0
    condensed_kg: float = 0.0
    heated_j: float = 0.0
    heating: bool = False
    vent_stage: int = 0
    dehumidifying: bool = False
    drier: bool = False

    def relative_humidity_pct(self) -> float:
        return float(relative_humidity_pct(self.temperature_c, self.humidity_g_kg))


@dataclass(frozen=True)
class _Steady:
    """What the house exchanges and is given at steady levels: its exchange
    with the outside through the glass, for each W/m²K of U (m³/s), the heat
    added (W), of it the heaters' (W), and the water taken (kg/s)."""

    glass_m3_s_per_u: float
    heat_w: float
    heater_w: float
    water_removed_kg_s: float


@dataclass(frozen=True)
class _Course:
    """How the house's air goes through a stretch: its temperature towards
    `settled_c` at `rate_s` per second while it exchanges air with the
    outside, or, shut off from it, by `warming_c_s` a second; with what it
    exchanges through its doors, vents and gaps (m³/s), `venting_s` of its
    air a second, its water towards the outside's, `outside_g_kg`, as its
    equipment takes `drying_g_kg_s` of it."""

    settled_c: float
    rate_s: float
    warming_c_s: float
    venting_m3_s: float
    venting_s: float = 0.0
    outside_g_kg: float = 0.0
    drying_g_kg_s: float = 0.0

    def temperature_c(self, start_c: float, duration_s: float) -> float:
        if self.rate_s > 0:
            return _towards(start_c, self.settled_c, self.rate_s, duration_s)
        return start_c + self.warming_c_s * duration_s

    def reaching_s(self, start_c: float, edge_c: float) -> float | None:
        """How long the air takes from `start_c` to `edge_c`, if it gets
        there: none if it goes the other way, or settles short of it."""
        if self.rate_s > 0:
            if not min(start_c, self.settled_c) <= edge_c <= max(start_c, self.settled_c):
                return None
            if edge_c == self.settled_c:
                return None
            return math.log((start_c - self.settled_c) / (edge_c - self.settled_c)) / self.rate_s
        if self.warming_c_s == 0 or (edge_c - start_c) / self.warming_c_s < 0:
            return None
        return (edge_c - start_c) / self.warming_c_s

    def water_g_kg(self, start_g_kg: float, duration_s: float) -> float:
        """The air's humidity ratio after `duration_s`, from `start_g_kg`:
        before equipment that takes more than the air holds is held to it,
        or saturation to what the air can hold."""
        if self.venting_s > 0:
            return _towards(
                start_g_kg,
                self.outside_g_kg - self.drying_g_kg_s / self.venting_s,
                self.venting_s,
                duration_s,
            )
        return start_g_kg - self.drying_g_kg_s * duration_s

    def water_reaching_s(self, start_g_kg: float, edge_g_kg: float) -> float | None:
        """How long the air's humidity ratio takes from `start_g_kg` to
        `edge_g_kg`, if it gets there: none if it goes the other way, or
        settles short of it."""
        if self.venting_s > 0:
            settled = self.outside_g_kg - self.drying_g_kg_s / self.venting_s
            if not min(start_g_kg, settled) <= edge_g_kg <= max(start_g_kg, settled):
                return None
            if edge_g_kg == settled:
                return None
            return math.log((start_g_kg - settled) / (edge_g_kg - settled)) / self.venting_s
        if self.drying_g_kg_s == 0 or (start_g_kg - edge_g_kg) / self.drying_g_kg_s < 0:
            return None
        return (start_g_kg - edge_g_kg) / self.drying_g_kg_s

    def humidity_reaching_s(
        self, start_c: float, start_g_kg: float, edge_pct: float, within_s: float
    ) -> float | None:
        """How long the air's relative humidity takes to reach `edge_pct`,
        from `start_c` and `start_g_kg`, if it does within `within_s`: where
        its humidity ratio meets what air at its temperature then holds at
        that relative humidity, the first time, found to a nanosecond. Each
        of the two moves as one exponential, so the edge is bracketed by
        moments a fraction of the quicker one's time apart, then halved."""

        def beyond(duration_s: float) -> float:
            temperature = self.temperature_c(start_c, duration_s)
            holds = float(humidity_ratio_g_kg(temperature, edge_pct))
            return self.water_g_kg(start_g_kg, duration_s) - holds

        before = beyond(0.0)
        if before == 0.0:
            return 0.0
        quickest = max(self.rate_s, self.venting_s, 1.0 / within_s)
        wanted = math.ceil(within_s * quickest * SAMPLES_A_RATE)
        samples = min(MOST_SAMPLES, max(FEWEST_SAMPLES, wanted))
        earlier = 0.0
        for sample in range(1, samples + 1):
            later = within_s * sample / samples
            if (beyond(later) > 0) != (before > 0):
                while later - earlier > HUMIDITY_EDGE_S:
                    middle = (earlier + later) / 2
                    if (beyond(middle) > 0) == (before > 0):
                        earlier = middle
                    else:
                        later = middle
                return later
            earlier = later
        return None


def _outside_water_g_kg(outside: WeatherState) -> float:
    """The outside air's humidity ratio, in g/kg."""
    return float(humidity_ratio_g_kg(outside.air_temperature_c, outside.relative_humidity_pct))


def _heating_switched(air: HouseAir) -> HouseAir:
    return replace(air, heating=not air.heating)


def _dehumidifier_switched(air: HouseAir) -> HouseAir:
    return replace(air, dehumidifying=not air.dehumidifying)


def _drier_switched(air: HouseAir) -> HouseAir:
    return replace(air, drier=not air.drier)


def _vents_to(stage: int) -> Callable[[HouseAir], HouseAir]:
    return lambda air: replace(air, vent_stage=stage)


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
        # Its air at every step worked through, each `STEP_S`, and those
        # moments in order, so that the latest before any other is found at
        # once, however long the run (P09.2). A moment asked for between
        # them is worked out from the step before it and not kept: the air
        # at a moment is the same whatever was asked for before.
        self._kept: dict[float, HouseAir] = {0.0: start}
        self._moments: list[float] = [0.0]
        # One request at a time works the house's air on; others wait for
        # it, and find what it kept.
        self._working = threading.RLock()
        # Held only to add to what is kept, or to copy it: another house
        # carrying on from this one copies it without waiting for a request
        # working this house's air on.
        self._keeping = threading.Lock()
        # The stretch a request is working the house's air through, from the
        # latest step kept before the moment asked for to it, or None: a
        # house carrying on from this one waits while the stretch covers
        # what it needs, rather than work it out beside this house. Told
        # under `_keeping`, and `_kept_changed` is notified when it ends.
        self._stretch: tuple[float, float] | None = None
        self._kept_changed = threading.Condition(self._keeping)
        # The houses this one carries on from (`carry_on_from`), each with
        # the moment up to which it is the same air: what they keep up to
        # then is taken over again whenever this house works its air on, so
        # that a request working one of them on is neither waited for nor
        # repeated. Held weakly: a house the kept runs have forgotten is not
        # kept alive by those that carried on from it.
        self._sources: list[tuple[weakref.ref[WholeHouse], float]] = []

    def _levels(self, time_s: float, air: HouseAir) -> dict[str, float]:
        """Its equipment's levels from `time_s`, the air being `air` then:
        as the schedule sets them, its thermostat's heater as the air has the
        thermostat run it, and its circulation loop's fans as its vents stand
        open."""
        levels = self.run.scheduled_levels_at(time_s)
        thermostat = self.run.thermostat
        if thermostat is not None and self.run.thermostat_governs(time_s):
            levels[thermostat.actuator_id] = ON if air.heating else OFF
        drying = self._dehumidifying(time_s)
        if drying is not None and drying.actuator_id in levels:
            levels[drying.actuator_id] = ON if air.dehumidifying else OFF
        control = self.run.control
        if control is None or control.circulation is None or control.venting is None:
            return levels
        fans = [
            fan
            for fan in control.circulation.fans
            if fan in levels and self.run.controls(fan, time_s)
        ]
        if fans:
            openings = self._openings(time_s, air)
            vents_level = max(openings.get(vent, 0.0) for vent in control.venting.vents)
            running = control.circulation.runs_at(control.venting, vents_level)
            levels |= dict.fromkeys(fans, ON if running else OFF)
        return levels

    def _dehumidifying(self, time_s: float) -> DehumidifyingLoop | None:
        """Its dehumidifying loop, while it runs its dehumidifier at
        `time_s`."""
        control = self.run.control
        drying = None if control is None else control.dehumidifying
        if drying is None or not self.run.controls(drying.actuator_id, time_s):
            return None
        return drying

    def _drying_vents(self, time_s: float) -> DehumidifyingLoop | None:
        """Its dehumidifying loop, while it may open the vents' first stage
        at `time_s`: one that vents, its venting loop running a vent then."""
        control = self.run.control
        drying = None if control is None else control.dehumidifying
        if drying is None or not drying.vents_when_drier or self._venting(time_s) is None:
            return None
        return drying

    def _venting(self, time_s: float) -> VentingLoop | None:
        """Its venting loop, while it runs one of its vents at `time_s`."""
        control = self.run.control
        venting = None if control is None else control.venting
        if venting is None or not any(self.run.controls(v, time_s) for v in venting.vents):
            return None
        return venting

    def _venting_to_c(self, time_s: float) -> float:
        """The temperature its venting loop vents to at `time_s`."""
        control = self.run.control
        assert control is not None and control.venting is not None
        return control.venting.setpoint_c(control.by_day(time_s))

    def _openings(self, time_s: float, air: HouseAir) -> dict[str, float]:
        """How far its doors and vents stand open from `time_s`, the air
        being `air` then: as the schedule has them, and its venting loop's
        vents at the stage the air has the loop open them to."""
        levels = self.run.scheduled_openings_at(time_s)
        venting = self._venting(time_s)
        if venting is None:
            return levels
        level = venting.level_at(air.vent_stage)
        drying = self._drying_vents(time_s)
        if drying is not None and drying.vents(
            dehumidifying=air.dehumidifying, heating=air.heating, drier=air.drier
        ):
            # For the air's water: the first stage, unless the vents stand
            # open further for its heat.
            level = max(level, venting.level_at(1))
        for vent in venting.vents:
            if vent in levels and self.run.controls(vent, time_s):
                levels[vent] = level
        return levels

    def _decided(self, time_s: float, air: HouseAir, outside: WeatherState) -> HouseAir:
        """`air`, with its loops' decisions at `time_s`, under the weather
        `outside`: its thermostat's, while it runs its heater, on below its
        band, off above it, as it was between; its venting loop's, each stage
        open above its edge and closed below it by the band, as it was
        between; and its dehumidifying loop's, its dehumidifier on above its
        band and off below it, and the air outside drier enough above its
        margin and not below it less its band, each as it was between."""
        thermostat = self.run.thermostat
        if thermostat is not None and self.run.thermostat_governs(time_s):
            heating = thermostat.heats(
                air.temperature_c, air.heating, time_s, self.run.schedule.targets_at(time_s)
            )
            if heating != air.heating:
                air = replace(air, heating=heating)
        venting = self._venting(time_s)
        if venting is not None:
            stage = venting.stage_at(air.temperature_c, air.vent_stage, self._venting_to_c(time_s))
            if stage != air.vent_stage:
                air = replace(air, vent_stage=stage)
        drying = self._dehumidifying(time_s)
        if drying is not None:
            on = drying.on_at(air.relative_humidity_pct(), air.dehumidifying)
            if on != air.dehumidifying:
                air = replace(air, dehumidifying=on)
        venting_drier = self._drying_vents(time_s)
        if venting_drier is not None:
            wetter_by = air.humidity_g_kg - _outside_water_g_kg(outside)
            drier = venting_drier.drier_at(wetter_by, air.drier)
            if drier != air.drier:
                air = replace(air, drier=drier)
        return air

    def _switching_s(
        self, air: HouseAir, course: _Course, time_s: float, within_s: float
    ) -> float | None:
        """How long, within `within_s` of `time_s`, until its thermostat
        switches its heater, as the air reaches its band's far edge: the top
        while it heats, the bottom while it does not; none if it does not."""
        thermostat = self.run.thermostat
        if thermostat is None or not self.run.thermostat_governs(time_s):
            return None
        half = thermostat.band_c / 2
        setpoint = thermostat.setpoint_c(time_s, self.run.schedule.targets_at(time_s))
        edge = setpoint + half if air.heating else setpoint - half
        reached = course.reaching_s(air.temperature_c, edge)
        return reached if reached is not None and reached < within_s else None

    def _switch(
        self, air: HouseAir, course: _Course, time_s: float, within_s: float
    ) -> tuple[float, Callable[[HouseAir], HouseAir]] | None:
        """The first of its loops to switch within `within_s` of `time_s`, as
        the air reaches one of their edges: how long until then, and the
        switch, made to the air then; its thermostat's first, of two at one
        moment. None if none switches."""
        switches: list[tuple[float, Callable[[HouseAir], HouseAir]]] = []
        heating = self._switching_s(air, course, time_s, within_s)
        if heating is not None:
            switches.append((heating, _heating_switched))
        venting = self._venting(time_s)
        if venting is not None:
            opens, closes = venting.edges_c(air.vent_stage, self._venting_to_c(time_s))
            for edge, step in ((opens, 1), (closes, -1)):
                reached = None if edge is None else course.reaching_s(air.temperature_c, edge)
                if reached is not None and reached < within_s:
                    switches.append((reached, _vents_to(air.vent_stage + step)))
        drying = self._dehumidifying(time_s)
        if drying is not None:
            reached = course.humidity_reaching_s(
                air.temperature_c,
                air.humidity_g_kg,
                drying.edge_pct(air.dehumidifying),
                within_s,
            )
            if reached is not None and reached < within_s:
                switches.append((reached, _dehumidifier_switched))
        venting_drier = self._drying_vents(time_s)
        if venting_drier is not None:
            edge = course.outside_g_kg + venting_drier.drier_edge_g_kg(air.drier)
            reached = course.water_reaching_s(air.humidity_g_kg, edge)
            if reached is not None and reached < within_s:
                switches.append((reached, _drier_switched))
        return min(switches, key=lambda switch: switch[0]) if switches else None

    def _through(
        self, air: HouseAir, start_s: float, end_s: float, until_s: float | None = None
    ) -> HouseAir:
        """The air through one stretch of its run, from `start_s` to `end_s`,
        or only to `until_s` within it: under the weather and the sun at its
        middle, its levels held but for those its loops run, each switched
        the moment the air reaches one of its loop's edges."""
        middle = (start_s + end_s) / 2
        outside = self.run.weather.at(middle)
        sun = self.run.solar_heat_total_w(middle)
        now, end = start_s, end_s if until_s is None else until_s
        air = self._decided(now, air, outside)
        while now < end:
            steady = self._held(self._levels(now, air))
            course = self._course(air, steady, outside, now, sun)
            switch = self._switch(air, course, now, end - now)
            span = end - now if switch is None else switch[0]
            air = self._advance(air, steady, outside, span, now, sun_w=sun, course=course)
            now = end if switch is None else now + span
            if switch is not None:
                air = switch[1](air)
        return air

    def _stretch_around(self, time_s: float) -> tuple[float, float]:
        """The stretch of its run `time_s` lies in, as the air is worked
        through: from the latest `STEP_S` or command at or before it, to the
        next after it."""
        step = math.floor(time_s / STEP_S) * STEP_S
        changes = self.run.schedule.moments_between(step, step + STEP_S)
        start = max([step, *(moment for moment in changes if moment <= time_s)])
        end = min([step + STEP_S, *(moment for moment in changes if moment > time_s)])
        return start, end

    def controlled_at(self, time_s: float) -> dict[str, float]:
        """The levels its controller runs its devices at, at `time_s`, as its
        air decides them: its heater, its vents and its fans, each from the
        moment its loop switched it; a device a command has taken over left
        out."""
        start, end = self._stretch_around(time_s)
        with self._working:
            air = self._through(self.air_at(start), start, end, time_s)
        levels = self._levels(time_s, air) | self._openings(time_s, air)
        return {
            device: level for device, level in levels.items() if self.run.controls(device, time_s)
        }

    def heater_level_at(self, time_s: float) -> float:
        """The level its thermostat runs its heater at, at `time_s`: on from
        the moment the air fell below its band, off from the moment it rose
        above it."""
        thermostat = self.run.thermostat
        if thermostat is None:
            raise ValueError("a house without a thermostat runs no heater by itself")
        start, end = self._stretch_around(time_s)
        with self._working:
            air = self._through(self.air_at(start), start, end, time_s)
        return ON if air.heating else OFF

    def _held(self, levels: Mapping[str, float]) -> _Steady:
        key = tuple(sorted(levels.items()))
        if key not in self._steady:
            terms = self.run.terms_for(levels)
            transport = self.run.transport_for(levels, openings={})
            air = self._air
            configured_u = self.run.settings.glazing_u_w_m2k
            glass = float(transport.glass_m3_s()[air].sum())
            self._steady[key] = _Steady(
                glass_m3_s_per_u=glass / configured_u if configured_u > 0 else 0.0,
                heat_w=float(terms.heat_w[air].sum()),
                heater_w=sum(
                    capability.power_w * levels.get(piece.actuator_id, 0.0)
                    for piece in self.run.equipment
                    for capability in piece.capabilities()
                    if isinstance(capability, Heats)
                ),
                water_removed_kg_s=float(terms.water_removed_kg_s[air].sum()),
            )
        return self._steady[key]

    def _course(
        self,
        air: HouseAir,
        steady: _Steady,
        outside: WeatherState,
        time_s: float,
        sun_w: float = 0.0,
    ) -> _Course:
        """How the air's temperature goes from `air`, at steady levels and
        under the weather `outside`, its doors and vents open as they are at
        `time_s`."""
        volume = self.volume_m3
        heat_per_k = AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K
        heat_w = steady.heat_w + sun_w
        settings = self.run.settings
        u = glazing_u_w_m2k(settings.glazing_u_w_m2k, outside.wind_speed_m_s)
        leaks_m3_s = settings.infiltration_per_s(outside.wind_speed_m_s) * volume
        levels = self._openings(time_s, air)
        sites = [vent.site_at(levels[vent.opening_id]) for vent in self.run.vents]
        through = opening_flows(
            [site for site in sites if site.aperture_m2 > 0], air.temperature_c, outside
        )
        entering = sum(max(flow.net_m3_s, 0.0) + flow.exchange_m3_s for flow in through)
        venting_m3_s = entering + leaks_m3_s
        exchange = u * steady.glass_m3_s_per_u + venting_m3_s
        air_kg = AIR_DENSITY_KG_M3 * volume
        return _Course(
            settled_c=outside.air_temperature_c
            + (heat_w / (heat_per_k * exchange) if exchange > 0 else 0.0),
            rate_s=exchange / volume,
            warming_c_s=heat_w / (heat_per_k * volume),
            venting_m3_s=venting_m3_s,
            venting_s=venting_m3_s / volume,
            outside_g_kg=_outside_water_g_kg(outside),
            drying_g_kg_s=steady.water_removed_kg_s * GRAMS_PER_KG / air_kg,
        )

    def _advance(
        self,
        air: HouseAir,
        steady: _Steady,
        outside: WeatherState,
        duration_s: float,
        time_s: float,
        *,
        sun_w: float = 0.0,
        course: _Course | None = None,
    ) -> HouseAir:
        volume = self.volume_m3
        course = course or self._course(air, steady, outside, time_s, sun_w)
        temperature = course.temperature_c(air.temperature_c, duration_s)
        air_kg = AIR_DENSITY_KG_M3 * volume
        water = course.water_g_kg(air.humidity_g_kg, duration_s)
        if course.venting_s > 0:
            co2 = _towards(air.co2_ppm, outside.co2_ppm, course.venting_s, duration_s)
        else:
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
            heated_j=air.heated_j + steady.heater_w * duration_s,
            heating=air.heating,
            vent_stage=air.vent_stage,
            dehumidifying=air.dehumidifying,
            drier=air.drier,
        )

    def carry_on_from(self, other: WholeHouse) -> None:
        """Take over the air `other` has worked out up to the first moment
        its schedule and this house's differ (`Schedule.same_until`): until
        then, both are the same air, so what `other` works out later up to
        then is taken over too, as this house works its own air on. Only
        another house under the same weather, with the same doors and vents,
        is the same air."""
        until = self.run.schedule.same_until(other.run.schedule)
        with self._working:
            self._sources = [(source, up_to) for source, up_to in self._sources if source()]
            self._sources.append((weakref.ref(other), until))
            self._take_over(until)

    def _take_over(self, time_s: float) -> None:
        """Take over, from each house carried on from, the steps it has kept
        up to `time_s` and past the latest this house has kept before then,
        as far as the two are the same air; while the other is working that
        very stretch, wait for it rather than work it out beside it. Called
        with `_working` held."""
        for source, until in self._sources:
            other = source()
            if other is None:
                continue
            up_to = min(time_s, until)
            while True:
                # Only this request writes what this house keeps: `_working`
                # is held. The two `_keeping` locks are never held together,
                # since two houses may carry on from each other.
                since = self._moments[bisect_right(self._moments, up_to) - 1]
                with other._kept_changed:
                    first = bisect_right(other._moments, since)
                    last = bisect_right(other._moments, up_to)
                    theirs = [
                        (moment, other._kept[moment]) for moment in other._moments[first:last]
                    ]
                    ahead = theirs[-1][0] if theirs else since
                    waiting = other._working_through(ahead, up_to)
                    if waiting:
                        other._kept_changed.wait(LOOK_AGAIN_S)
                for moment, air in theirs:
                    self._keep(moment, air)
                if not waiting:
                    break

    def _working_through(self, since: float, up_to: float) -> bool:
        """Whether a request is working this house's air through a step past
        `since` and up to `up_to`, which a house carrying on from this one
        would otherwise work out itself. Called with `_keeping` held."""
        if self._stretch is None:
            return False
        start, end = self._stretch
        return start < up_to and since < min(end, up_to)

    def seed(self, moment_s: float, air: HouseAir) -> None:
        """Take `air` as this house's at `moment_s`, from a checkpoint of the
        same run (P09.5): later moments carry on from it, unless the house
        has worked out its own there."""
        with self._working:
            if moment_s not in self._kept:
                self._keep(moment_s, air)

    def mean_between(self, from_s: float, until_s: float) -> HouseAir:
        """The house's mean air from `from_s` to `until_s`: its temperature,
        humidity ratio and CO₂ every `STEP_S` from `from_s`, and at
        `until_s`, averaged by the trapezoid rule; with the water it has lost
        by `until_s`."""
        if until_s <= from_s:
            raise ValueError("a mean is taken over a stretch of a run")
        steps = math.ceil((until_s - from_s) / STEP_S)
        moments = [min(from_s + step * STEP_S, until_s) for step in range(steps + 1)]
        airs = [self.air_at(moment) for moment in moments]
        spans = np.diff(moments)

        def mean(values: Sequence[float]) -> float:
            pairs = np.asarray(values)
            return float(((pairs[:-1] + pairs[1:]) / 2 * spans).sum() / (until_s - from_s))

        return HouseAir(
            temperature_c=mean([air.temperature_c for air in airs]),
            humidity_g_kg=mean([air.humidity_g_kg for air in airs]),
            co2_ppm=mean([air.co2_ppm for air in airs]),
            removed_kg=airs[-1].removed_kg,
            condensed_kg=airs[-1].condensed_kg,
            heated_j=airs[-1].heated_j,
            heating=airs[-1].heating,
            vent_stage=airs[-1].vent_stage,
            dehumidifying=airs[-1].dehumidifying,
            drier=airs[-1].drier,
        )

    def heated_j(self, from_s: float, until_s: float) -> float:
        """The heat its heaters give its air from `from_s` to `until_s`, in
        J: their rated power at the levels they run at, for as long."""
        return self.air_at(until_s).heated_j - self.air_at(from_s).heated_j

    def air_at(self, time_s: float) -> HouseAir:
        """The house's air at `time_s`, from the latest moment kept before
        it, a stretch at a time, at most `STEP_S` long and ending at each of
        its schedule's changes."""
        if time_s < 0:
            raise ValueError("a climate run starts at 0 s")
        with self._working:
            return self._worked_to(time_s)

    def _keep(self, moment: float, air: HouseAir) -> None:
        with self._keeping:
            if moment not in self._kept:
                insort(self._moments, moment)
            self._kept[moment] = air

    def _worked_to(self, time_s: float) -> HouseAir:
        self._take_over(time_s)
        start = self._moments[bisect_right(self._moments, time_s) - 1]
        if start == time_s:
            return self._kept[start]
        with self._keeping:
            self._stretch = (start, time_s)
        try:
            return self._worked_on(start, time_s)
        finally:
            with self._kept_changed:
                self._stretch = None
                self._kept_changed.notify_all()

    def _worked_on(self, start: float, time_s: float) -> HouseAir:
        air = self._kept[start]
        changes = set(self.run.schedule.moments_between(start, time_s))
        steps = {
            (math.floor(start / STEP_S) + n) * STEP_S
            for n in range(1, int(time_s // STEP_S) - int(start // STEP_S) + 1)
        }
        now = start
        for until in sorted(changes | steps | {time_s}):
            if until > now:
                air = self._through(air, now, until)
                now = until
                if until in steps:
                    self._keep(until, air)
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
