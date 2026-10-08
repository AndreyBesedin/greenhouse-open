"""A climate run: a scenario's air through time, on its own clock (P05.3).

A run starts from the scenario's base airflow and its air at one starting
temperature and humidity everywhere (`climate.settings`), its equipment as
its schedule sets it at the start, and applies each later command at its
moment (`climate.commands`). Between two moments the levels hold, and so
does the flow: the base airflow plus the fans' jets, made to conserve mass
(`climate.projection`). The air's temperature and water are carried by it,
warmed and dried by the equipment, and its heat exchanged with the outside
(`climate.transport`).

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
so that a slice or a legend shows the air's.
"""

import math
import threading
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.projection import FaceFlows, conserving, face_flows
from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg, relative_humidity_pct
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.climate.sources import SourceTerms, source_terms
from greenhouse_sim.climate.transport import AirState, Transport
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, EnvironmentField, FieldGrid
from greenhouse_sim.world.equipment import Equipment

type _Levels = tuple[tuple[str, float], ...]
# A run keeps its air this often on the way to a moment, in seconds.
KEEP_EVERY_S: Final = 60.0
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


class ClimateRun:
    """A scenario's air from its start under a schedule, over a grid whose
    `solid` cells obstacles fill, in its order (z, y, x)."""

    def __init__(
        self,
        base: AirflowModel,
        equipment: Sequence[Equipment],
        schedule: Schedule,
        settings: ClimateSettings,
        grid: FieldGrid,
        solid: np.ndarray,
        vents: Sequence[Vent] = (),
    ) -> None:
        nx, ny, nz = grid.shape
        if solid.shape != (nz, ny, nx):
            raise ValueError(f"the solid cells are {solid.shape}, not the grid's {(nz, ny, nx)}")
        self.base = base
        self.equipment = list(equipment)
        self.schedule = schedule
        self.settings = settings
        self.grid = grid
        self.solid = solid
        self.vents = tuple(vents)
        self._base_velocity = base.field("base", grid).channels[AirQuantity.VELOCITY]
        self._steady: dict[_Levels, tuple[SourceTerms, FaceFlows, Transport]] = {}
        self._working = threading.RLock()
        start = humidity_ratio_g_kg(settings.start_temperature_c, settings.start_humidity_pct)
        self._kept: dict[float, AirState] = {
            0.0: AirState(
                temperature=np.full((nz, ny, nx), settings.start_temperature_c),
                humidity=np.full((nz, ny, nx), float(start)),
                co2=np.full((nz, ny, nx), settings.start_co2_ppm),
            )
        }

    def levels_at(self, time_s: float) -> dict[str, float]:
        """Each piece of equipment's level at `time_s`."""
        return self.schedule.levels_at([piece.actuator_id for piece in self.equipment], time_s)

    def _held(self, levels: Mapping[str, float]) -> tuple[SourceTerms, FaceFlows, Transport]:
        """What the equipment does at steady levels: its source terms, the
        flow it makes with the base airflow, and how that moves heat."""
        key = tuple(sorted(levels.items()))
        with self._working:
            return self._steady_at(key, levels)

    def _steady_at(
        self, key: _Levels, levels: Mapping[str, float]
    ) -> tuple[SourceTerms, FaceFlows, Transport]:
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
            transport = Transport(self.grid, flows, self.solid, self.settings, self.vents)
            self._steady[key] = (terms, flows, transport)
        return self._steady[key]

    def terms_at(self, time_s: float) -> SourceTerms:
        """What the equipment adds to the air at `time_s`."""
        return self._held(self.levels_at(time_s))[0]

    def flows_at(self, time_s: float) -> FaceFlows:
        """The air's flow through the grid's faces at `time_s`."""
        return self._held(self.levels_at(time_s))[1]

    def transport_at(self, time_s: float) -> Transport:
        """How heat moves at `time_s`."""
        return self._held(self.levels_at(time_s))[2]

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
        if time_s < 0:
            raise ValueError("a climate run starts at 0 s")
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
                terms, _, transport = self._held(self.levels_at(now))
                air = transport.advance(air, terms, until - now)
                now = until
                if until in kept:
                    self._kept[until] = air
        self._kept[time_s] = air
        return air

    def temperature_at(self, time_s: float) -> np.ndarray:
        """The air's temperature in every cell at `time_s`."""
        return self.air_at(time_s).temperature

    def _draughts(self, air: AirState) -> np.ndarray:
        """The draughts through the open doors and vents, as the air against
        each is warmer or cooler than the outside's."""
        nx, ny, nz = self.grid.shape
        draughts = np.zeros((nz, ny, nx, VECTOR_COMPONENTS))
        for vent in self.vents:
            draughts += vent.draught(
                self.grid,
                air.temperature,
                self.settings.outside_temperature_c,
                self.settings.vent_exchange_m_s,
            )
        return draughts

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        """The air at `time_s`: its velocity, with the draughts through open
        doors and vents, its temperature, its relative humidity and its
        CO2."""
        if grid != self.grid:
            raise ValueError("a climate run is drawn on its own grid")
        air = self.air_at(time_s)
        temperature = _filled(air.temperature, self.solid)
        humidity = _filled(air.humidity, self.solid)
        return EnvironmentField(
            field_id=field_id,
            source=f"climate:{self.base.field(field_id, grid).source}",
            grid=grid,
            time_s=time_s,
            channels={
                AirQuantity.VELOCITY: self.flows_at(time_s).velocity() + self._draughts(air),
                AirQuantity.TEMPERATURE: temperature,
                AirQuantity.HUMIDITY: relative_humidity_pct(temperature, humidity),
                AirQuantity.CO2: _filled(air.co2, self.solid),
            },
        )
