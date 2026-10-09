"""A climate run: a scenario's air through time, on its own clock (P05.3).

A run starts from the scenario's base airflow and its air at one starting
temperature and humidity everywhere (`climate.settings`), its equipment as
its schedule sets it at the start, and applies each later command at its
moment (`climate.commands`). Between two moments the levels hold, and so
does the flow: the base airflow plus the fans' jets, made to conserve mass
(`climate.projection`). The air's temperature and water are carried by it,
warmed and dried by the equipment, and exchanged with the outside
(`climate.transport`): the weather at the middle of each stretch advanced,
at most a minute long (`greenhouse_sim.weather`).

The same schedule always gives the same air at the same moments, so a run
may take over another's air up to the first moment their schedules differ
(`carry_on_from`). A run keeps the air at every moment it was asked for,
and every minute on the way to one, so that a later moment carries on from
the latest before it, and an earlier one, or a probe's reading every
minute, is found kept. One request at a time works a run on; others wait
for it, and find what it kept.

As a field (`field`), the air at a moment is its velocity, temperature,
relative humidity (`climate.psychrometrics`) and CO2 there. A cell an obstacle fills
is still, and shows the mean temperature and water of the cells beside it,
so that a slice or a legend shows the air's. A run under the sun
(`greenhouse_sim.solar.inside`) adds the light on a level surface at each
cell's centre: its PAR and its shortwave irradiance.

The sun warms the air (P08.8): of the light reaching the floor under each
column, the shortwave the glass and the shade let through, the air in the
column's lowest cell takes `SOLAR_HEAT_SHARE` as heat, at the middle of
each stretch, as it takes the equipment's.
"""

import math
import threading
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Final

import numpy as np

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.glazing import GlazedCells, GlazingAt, glazing_at
from greenhouse_sim.climate.openings import OpeningFlow, opening_flows
from greenhouse_sim.climate.projection import FaceFlows, conserving, face_flows
from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg, relative_humidity_pct
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.climate.sources import SourceTerms, source_terms
from greenhouse_sim.climate.transport import AirState, Transport
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, EnvironmentField, FieldGrid
from greenhouse_sim.solar.inside import Sunlight
from greenhouse_sim.weather.sources import RunWeather
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.equipment import Equipment

type _Levels = tuple[tuple[str, float], ...]
# A run keeps its air this often on the way to a moment, in seconds.
KEEP_EVERY_S: Final = 60.0
# The share of the sun's light reaching the floor that the air above it
# takes as heat; the ground and the crop's water take the rest (P08.8).
SOLAR_HEAT_SHARE: Final = 0.7
# How many times solid cells take their neighbours' mean: enough to reach the
# middle of an obstacle eight cells thick.
_FILLING_PASSES: Final = 4


# A cell's six neighbours, as offsets (z, y, x).
_BESIDE: Final = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _filled(temperature: np.ndarray, solid: np.ndarray) -> np.ndarray:
    """The temperature with each solid cell given the mean of the cells beside
    it that have one, pass by pass from the obstacle's faces inwards."""
    shown = np.where(solid, 0.0, temperature)
    known = ~solid
    nz, ny, nx = shown.shape
    for _ in range(_FILLING_PASSES):
        if known.all():
            break
        values = np.pad(np.where(known, shown, 0.0), 1)
        counts = np.pad(known.astype(float), 1)
        total = np.zeros_like(shown)
        count = np.zeros_like(shown)
        for dz, dy, dx in _BESIDE:
            window = (
                slice(1 + dz, 1 + dz + nz),
                slice(1 + dy, 1 + dy + ny),
                slice(1 + dx, 1 + dx + nx),
            )
            total += values[window]
            count += counts[window]
        reached = ~known & (count > 0)
        shown = np.where(reached, total / np.maximum(count, 1.0), shown)
        known = known | reached
    return np.where(known, shown, temperature)


def _lowest_air(solid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The lowest cell of air in each column of the grid that has one, as
    indices (z, y, x)."""
    air = ~solid
    has_air = air.any(axis=0)
    lowest = air.argmax(axis=0)
    ys, xs = np.nonzero(has_air)
    return lowest[ys, xs], ys, xs


class ClimateRun:
    """A scenario's air from its start under a schedule and a weather, over a
    grid whose `solid` cells obstacles fill, in its order (z, y, x)."""

    def __init__(
        self,
        base: AirflowModel,
        equipment: Sequence[Equipment],
        schedule: Schedule,
        settings: ClimateSettings,
        grid: FieldGrid,
        solid: np.ndarray,
        weather: RunWeather,
        vents: Sequence[Vent] = (),
        glazed: Mapping[str, GlazedCells] | None = None,
        sunlight: Sunlight | None = None,
    ) -> None:
        nx, ny, nz = grid.shape
        if solid.shape != (nz, ny, nx):
            raise ValueError(f"the solid cells are {solid.shape}, not the grid's {(nz, ny, nx)}")
        self.base = base
        self.equipment = list(equipment)
        self.schedule = schedule
        self.settings = settings
        self.weather = weather
        self.grid = grid
        self.solid = solid
        self.vents = tuple(vents)
        self.glazed = dict(glazed or {})
        self.sunlight = sunlight
        self._floor_cells = _lowest_air(solid)
        self._base_velocity = base.field("base", grid).channels[AirQuantity.VELOCITY]
        self._steady: dict[_Levels, tuple[SourceTerms, FaceFlows]] = {}
        self._through_flows: dict[str, FaceFlows] | None = None
        # When its air starts: at the start of the scenario's runs, unless it
        # is started later (`started_at`).
        self.start_s = 0.0
        self._working = threading.RLock()
        start = humidity_ratio_g_kg(settings.start_temperature_c, settings.start_humidity_pct)
        self._kept: dict[float, AirState] = {
            0.0: AirState(
                temperature=np.full((nz, ny, nx), settings.start_temperature_c),
                humidity=np.full((nz, ny, nx), float(start)),
                co2=np.full((nz, ny, nx), settings.start_co2_ppm),
            )
        }

    def started_at(self, start_s: float, air: AirState) -> ClimateRun:
        """The same run, under the same schedule and weather, but with its air
        starting at `start_s` as `air`: the grid run for a later part of a
        day (`greenhouse_sim.climate.day`). What its equipment does at steady
        levels is shared with this run, as it is the same."""
        later = ClimateRun(
            self.base,
            self.equipment,
            self.schedule,
            self.settings,
            self.grid,
            self.solid,
            self.weather,
            self.vents,
            self.glazed,
            self.sunlight,
        )
        later._steady = self._steady
        later._through_flows = self._through_flows
        later.start_s = start_s
        later._kept = {start_s: air}
        return later

    def levels_at(self, time_s: float) -> dict[str, float]:
        """Each piece of equipment's level at `time_s`."""
        return self.schedule.levels_at([piece.actuator_id for piece in self.equipment], time_s)

    def _held(self, levels: Mapping[str, float]) -> tuple[SourceTerms, FaceFlows]:
        """What the equipment does at steady levels: its source terms, and the
        flow it makes with the base airflow."""
        key = tuple(sorted(levels.items()))
        with self._working:
            return self._steady_at(key, levels)

    def _steady_at(
        self, key: _Levels, levels: Mapping[str, float]
    ) -> tuple[SourceTerms, FaceFlows]:
        if key not in self._steady:
            terms = SourceTerms.none(self.grid)
            for piece in self.equipment:
                terms = terms + source_terms(
                    piece, levels.get(piece.actuator_id, 0.0), self.grid, self.solid
                )
            flows = conserving(
                face_flows(self.grid, self._base_velocity + terms.velocity, self.solid),
                self.solid,
            )
            self._steady[key] = (terms, flows)
        return self._steady[key]

    def _through(self) -> dict[str, FaceFlows]:
        """The flow across the house of a cubic metre a second in through
        each open door or vent but the first, and out through the first: what
        the openings' net flows add to the flow, in proportion."""
        if self._through_flows is None:
            vents = [vent for vent in self.vents if vent.cells.any()]
            nx, ny, nz = self.grid.shape
            still = face_flows(self.grid, np.zeros((nz, ny, nx, VECTOR_COMPONENTS)), self.solid)
            self._through_flows = {
                vent.opening_id: conserving(
                    still, self.solid, inflow=vent.spread(1.0) - vents[0].spread(1.0)
                )
                for vent in vents[1:]
            }
        return self._through_flows

    def opening_levels_at(self, time_s: float) -> dict[str, float]:
        """How far each of its doors and vents stands open at `time_s`: as
        far as it is opened at the start, until a command moves it."""
        levels = {vent.opening_id: vent.opening.opening for vent in self.vents}
        for command in self.schedule.applied(time_s):
            if command.actuator_id in levels:
                levels[command.actuator_id] = command.level
        return levels

    def openings_for(
        self, air: AirState, outside: WeatherState, time_s: float
    ) -> dict[str, OpeningFlow]:
        """What each door and vent open at `time_s` passes for `air`, by its
        mean temperature, under the weather `outside`."""
        levels = self.opening_levels_at(time_s)
        sites = [vent.site_at(levels[vent.opening_id]) for vent in self.vents]
        open_sites = [site for site in sites if site.aperture_m2 > 0]
        if not open_sites:
            return {}
        inside_c = float(air.temperature[~self.solid].mean())
        flows = opening_flows(open_sites, inside_c, outside)
        return {flow.opening_id: flow for flow in flows}

    def _flowing(self, flows: FaceFlows, openings: Mapping[str, OpeningFlow]) -> FaceFlows:
        """The equipment's flow with the openings' net flows across the
        house added."""
        through = self._through()
        added = [flow.copy() for flow in flows.flows]
        for opening_id, response in through.items():
            net = openings[opening_id].net_m3_s if opening_id in openings else 0.0
            if net != 0:
                for axis in (0, 1, 2):
                    added[axis] += net * response.flows[axis]
        return FaceFlows(grid=flows.grid, flows=(added[0], added[1], added[2]))

    def _transport(
        self, time_s: float, openings: Mapping[str, OpeningFlow]
    ) -> tuple[SourceTerms, Transport]:
        terms, flows = self._held(self.levels_at(time_s))
        transport = Transport(
            self.grid,
            self._flowing(flows, openings),
            self.solid,
            self.settings,
            self.vents,
            openings,
        )
        return terms, transport

    def terms_at(self, time_s: float) -> SourceTerms:
        """What the equipment adds to the air at `time_s`."""
        return self._held(self.levels_at(time_s))[0]

    def solar_heat_w(self, time_s: float) -> np.ndarray | None:
        """The heat the sun's light adds to the air at `time_s`, cell by cell,
        in W: `SOLAR_HEAT_SHARE` of what reaches the floor under each
        column, in the column's lowest cell of air; None while it adds
        none, at night, or without the sun."""
        if self.sunlight is None:
            return None
        floor = self.sunlight.floor_irradiance(time_s)
        if not floor.any():
            return None
        size = self.grid.cell_size
        zs, ys, xs = self._floor_cells
        heat = np.zeros(self.solid.shape)
        heat[zs, ys, xs] = SOLAR_HEAT_SHARE * floor[ys, xs] * size.x * size.y
        return heat

    def solar_heat_total_w(self, time_s: float) -> float:
        """All the heat the sun's light adds to the air at `time_s`, in W."""
        heat = self.solar_heat_w(time_s)
        return 0.0 if heat is None else float(heat.sum())

    def flows_at(
        self, time_s: float, openings: Mapping[str, OpeningFlow] | None = None
    ) -> FaceFlows:
        """The air's flow through the grid's faces at `time_s`, with what the
        doors and vents pass, as the air then drives them unless given."""
        return self.transport_at(time_s, openings).flows

    def transport_at(
        self, time_s: float, openings: Mapping[str, OpeningFlow] | None = None
    ) -> Transport:
        """How heat moves at `time_s`, with what the doors and vents pass, as
        the air then drives them unless given."""
        if openings is None:
            openings = self.openings_for(self.air_at(time_s), self.weather.at(time_s), time_s)
        return self._transport(time_s, openings)[1]

    def carry_on_from(self, other: ClimateRun) -> None:
        """Take over the air `other` has kept up to the first moment its
        schedule and this run's differ: until then, both runs are the same
        air."""
        mine, theirs = self.schedule.commands, other.schedule.commands
        differing = next(
            (index for index, (a, b) in enumerate(zip(mine, theirs, strict=False)) if a != b),
            min(len(mine), len(theirs)),
        )
        moments = [command.time_s for command in (*mine[differing:], *theirs[differing:])]
        until = min(moments, default=math.inf)
        with self._working, other._working:
            for moment, air in other._kept.items():
                if moment <= until:
                    self._kept.setdefault(moment, air)

    def air_at(self, time_s: float) -> AirState:
        """The air in every cell at `time_s`, from the latest moment kept
        before it."""
        if time_s < self.start_s:
            raise ValueError(f"this climate run starts at {self.start_s:g} s")
        with self._working:
            return self._worked_to(time_s)

    def _worked_to(self, time_s: float) -> AirState:
        start = max(moment for moment in self._kept if moment <= time_s)
        air = self._kept[start]
        changes = {moment for moment in self.schedule.moments() if start < moment <= time_s}
        minutes = int(time_s // KEEP_EVERY_S) - int(start // KEEP_EVERY_S)
        kept = {
            (int(start // KEEP_EVERY_S) + step) * KEEP_EVERY_S for step in range(1, minutes + 1)
        }
        now = start
        for until in sorted(changes | kept | {time_s}):
            if until > now:
                middle = (now + until) / 2
                outside = self.weather.at(middle)
                terms, transport = self._transport(now, self.openings_for(air, outside, now))
                sun = self.solar_heat_w(middle)
                if sun is not None:
                    terms = replace(terms, heat_w=terms.heat_w + sun)
                air = transport.advance(air, terms, until - now, outside)
                now = until
                if until in kept:
                    self._kept[until] = air
        self._kept[time_s] = air
        return air

    def temperature_at(self, time_s: float) -> np.ndarray:
        """The air's temperature in every cell at `time_s`."""
        return self.air_at(time_s).temperature

    def _draughts(
        self, air: AirState, outside: WeatherState, openings: Mapping[str, OpeningFlow]
    ) -> np.ndarray:
        """The draughts through the open doors and vents (`Vent.draught`)."""
        nx, ny, nz = self.grid.shape
        draughts = np.zeros((nz, ny, nx, VECTOR_COMPONENTS))
        for vent in self.vents:
            flow = openings.get(vent.opening_id)
            if flow is not None:
                draughts += vent.draught(
                    self.grid, flow, air.temperature, outside.air_temperature_c
                )
        return draughts

    def glazing_at(self, time_s: float) -> GlazingAt:
        """Each glazed surface at `time_s`: the air against it, its own
        temperature, and the heat it passes (`climate.glazing`)."""
        return glazing_at(
            self.glazed,
            self.air_at(time_s).temperature,
            self.weather.at(time_s),
            self.settings.glazing_u_w_m2k,
            time_s,
        )

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        """The air at `time_s`: its velocity, with the draughts through open
        doors and vents, its temperature, its relative humidity and its
        CO2."""
        if grid != self.grid:
            raise ValueError("a climate run is drawn on its own grid")
        return self.field_of(self.air_at(time_s), field_id, time_s)

    def field_of(self, air: AirState, field_id: str, time_s: float) -> EnvironmentField:
        """`air` as the field at `time_s`, in this run's flow then."""
        outside = self.weather.at(time_s)
        openings = self.openings_for(air, outside, time_s)
        velocity = self.flows_at(time_s, openings).velocity() + self._draughts(
            air, outside, openings
        )
        temperature = _filled(air.temperature, self.solid)
        humidity = _filled(air.humidity, self.solid)
        channels = {
            AirQuantity.VELOCITY: velocity,
            AirQuantity.TEMPERATURE: temperature,
            AirQuantity.HUMIDITY: relative_humidity_pct(temperature, humidity),
            AirQuantity.CO2: _filled(air.co2, self.solid),
        }
        if self.sunlight is not None:
            light = self.sunlight.at(time_s)
            channels[AirQuantity.PAR] = light.par_umol_m2_s
            channels[AirQuantity.IRRADIANCE] = light.irradiance_w_m2
        return EnvironmentField(
            field_id=field_id,
            source=f"climate:{self.base.field(field_id, self.grid).source}",
            grid=self.grid,
            time_s=time_s,
            channels=channels,
        )
