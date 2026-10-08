"""The air's temperature, water and CO2, carried and mixed over a field's
grid (P05.3, P05.4, P06.2).

The air's temperature, humidity ratio and CO2 in every cell are advanced
through time by finite volumes: what flows in through each face of a cell, what
mixing brings across it, what equipment adds or takes in it, and, for a
cell against the walls or the roof, the heat the glazing passes to or from
the outside.

- **Advection** is first-order upwind, by the flow through each face, made
  to conserve mass (`climate.projection`); none crosses the grid's faces, or
  into a cell an obstacle fills. A cell takes on the temperature of the air
  flowing in, F (T_upwind − T), so that uniform air stays uniform, and every
  new temperature lies between the old ones around it.
- **Mixing** between neighbouring air cells: the scenario's effective
  diffusivity times the face's area over the cells' distance, κ A / h.
- **Heat added** by equipment, its source terms (`climate.sources`), warms
  its cells by what their air can hold: ρ c_p V.
- **Water removed** by equipment dries its cells, never by more than a
  cell's air holds.
- **Condensation:** air holds no more water than saturates it at its
  temperature (`climate.psychrometrics`), checked every `CONDENSING_S` and
  at the end; what it would hold beyond condenses, on the cold glass, and is
  counted. Its latent heat is not.
- **The envelope:** a cell against a wall or the roof exchanges U A (T_out −
  T) with the outside through the face it lies against, both ways. The floor
  is not glass, and passes nothing. Glass passes no water.
- **Open doors and vents** (`climate.vents`) exchange the air against them
  with the outside's, its heat, its water and its CO2. Nothing else adds or
  takes CO2 yet.
- **The time step** keeps every cell's new temperature a weighted mean of the
  old ones: the air flowing in, the mixing and the exchange take at most
  half a cell's temperature away per step, which holds both the air crossing
  at most half a cell and explicit mixing's limit.

With the envelope shut (U = 0), the heat the air gains is what equipment
adds, and the water it loses what equipment removes and what condenses:
exactly in still air, and to the projection's tolerance in a flow.

Cells obstacles fill are not air: they are left as they start, and count for
nothing.
"""

import math
from dataclasses import dataclass
from typing import Final

import numpy as np

from greenhouse_sim.climate.projection import FaceFlows
from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg, saturation_ratio_g_kg
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.climate.sources import SourceTerms
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.fields.field import FieldGrid

AIR_DENSITY_KG_M3: Final = 1.2
AIR_HEAT_CAPACITY_J_KG_K: Final = 1005.0
# Each step takes at most this share of a cell's temperature away.
STEP_SHARE: Final = 0.5
# The longest step, when nothing moves or mixes fast enough to need shorter.
LONGEST_STEP_S: Final = 10.0
GRAMS_PER_KG: Final = 1000.0
# How often air beyond saturation condenses, in simulated seconds: often
# enough that little supersaturated air is carried, and far less often than
# a fan's steps, a twentieth of a second.
CONDENSING_S: Final = 10.0


@dataclass(frozen=True, eq=False)
class AirState:
    """The air in every cell of a grid, in its order (z, y, x): its
    temperature (°C), humidity ratio (g of water per kg of air) and CO2
    (ppm), with the water it has lost so far to equipment and to
    condensation, in kg."""

    temperature: np.ndarray
    humidity: np.ndarray
    co2: np.ndarray
    removed_kg: float = 0.0
    condensed_kg: float = 0.0


@dataclass(frozen=True, eq=False)
class Transport:
    """How heat moves over a grid, whose `solid` cells obstacles fill, in a
    steady flow through its faces (`greenhouse_sim.climate.projection`),
    between equipment's changes."""

    grid: FieldGrid
    flows: FaceFlows
    solid: np.ndarray
    settings: ClimateSettings
    vents: tuple[Vent, ...] = ()

    def __post_init__(self) -> None:
        nx, ny, nz = self.grid.shape
        if self.solid.shape != (nz, ny, nx) or self.flows.grid != self.grid:
            raise ValueError("the flow and the solid cells must cover the grid")

    def cell_volume_m3(self) -> float:
        size = self.grid.cell_size
        return size.x * size.y * size.z

    def _face_area(self, axis: int) -> float:
        size = self.grid.cell_size
        sides = {2: size.y * size.z, 1: size.x * size.z, 0: size.x * size.y}
        return sides[axis]

    def _spacing(self, axis: int) -> float:
        size = self.grid.cell_size
        return {2: size.x, 1: size.y, 0: size.z}[axis]

    def _takes(
        self,
    ) -> list[tuple[int, tuple[slice, ...], tuple[slice, ...], np.ndarray, np.ndarray]]:
        """For each axis, where its faces' lower and upper cells lie, and what
        each takes in per kelvin across the face, m³/s: the air flowing into
        it, and the mixing, nothing where either cell is solid."""
        air = ~self.solid
        takes = []
        for axis, low, high, flow in self.flows.faces():
            mixing = np.where(
                air[low] & air[high],
                self.settings.mixing_m2_s * self._face_area(axis) / self._spacing(axis),
                0.0,
            )
            # Into the lower cell when the flow is negative, the upper when
            # positive; mixing takes from both.
            takes.append(
                (axis, low, high, np.maximum(-flow, 0.0) + mixing, np.maximum(flow, 0.0) + mixing)
            )
        return takes

    def exchange_m3_s(self) -> np.ndarray:
        """Each cell's exchange with the outside through the walls and roof it
        lies against, U A / (ρ c_p), in m³/s of air brought to the outside's
        temperature each second; nothing for a solid cell."""
        nx, ny, nz = self.grid.shape
        exchange = np.zeros((nz, ny, nx))
        u = self.settings.glazing_u_w_m2k / (AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K)
        exchange[:, :, 0] += u * self._face_area(2)
        exchange[:, :, -1] += u * self._face_area(2)
        exchange[:, 0, :] += u * self._face_area(1)
        exchange[:, -1, :] += u * self._face_area(1)
        # The roof, over the top layer; the floor passes nothing.
        exchange[-1, :, :] += u * self._face_area(0)
        exchange += self.vents_m3_s()
        exchange[self.solid] = 0.0
        return exchange

    def vents_m3_s(self) -> np.ndarray:
        """The outside air each cell takes in through open doors and vents,
        and gives out, in m³/s; nothing for a solid cell."""
        nx, ny, nz = self.grid.shape
        exchange = np.zeros((nz, ny, nx))
        for vent in self.vents:
            exchange += vent.exchange_m3_s(self.settings.vent_exchange_m_s)
        exchange[self.solid] = 0.0
        return exchange

    def step_s(self) -> float:
        """The longest step that keeps every new temperature a weighted mean
        of the old ones, within `STEP_SHARE`."""
        taken = self.exchange_m3_s()
        for _, low, high, into_low, into_high in self._takes():
            taken[low] += into_low
            taken[high] += into_high
        fastest = float(taken.max()) / self.cell_volume_m3()
        return LONGEST_STEP_S if fastest <= 0 else min(LONGEST_STEP_S, STEP_SHARE / fastest)

    def advance(self, air: AirState, terms: SourceTerms, duration_s: float) -> AirState:
        """The air after `duration_s`, with equipment adding and taking what
        its source terms say in each cell, in equal steps no longer than
        `step_s`."""
        if duration_s <= 0:
            return air
        steps = math.ceil(duration_s / self.step_s())
        dt = duration_s / steps
        share = dt / self.cell_volume_m3()
        takes = [
            (axis, low, high, share * into_low, share * into_high)
            for axis, low, high, into_low, into_high in self._takes()
        ]
        exchange = share * self.exchange_m3_s()
        venting = share * self.vents_m3_s()
        outside = self.settings.outside_temperature_c
        outside_water = float(humidity_ratio_g_kg(outside, self.settings.outside_humidity_pct))
        outside_co2 = self.settings.outside_co2_ppm
        air_kg = AIR_DENSITY_KG_M3 * self.cell_volume_m3()
        solid = self.solid
        added = (
            share
            * np.where(solid, 0.0, terms.heat_w)
            / (AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K)
        )
        # What equipment would take each step, in grams per kilogram.
        drying = dt * np.where(solid, 0.0, terms.water_removed_kg_s) * GRAMS_PER_KG / air_kg
        condensing_every = max(1, round(CONDENSING_S / dt))
        # Temperature, water and CO2, carried together: one pass over the faces.
        carried = np.stack([air.temperature, air.humidity, air.co2])
        temperature, humidity, co2 = carried[0], carried[1], carried[2]
        # A solid cell's change is nothing: no face of it carries or mixes,
        # and nothing is added to it, taken from it or exchanged with it.
        drying_any = bool(drying.any())
        faces = [
            (axis + 1, (slice(None), *low), (slice(None), *high), into_low, into_high)
            for axis, low, high, into_low, into_high in takes
        ]
        removed = np.zeros_like(humidity)
        condensed = np.zeros_like(humidity)
        change = np.empty_like(carried)
        for step in range(1, steps + 1):
            np.multiply(exchange, outside - temperature, out=change[0])
            change[0] += added
            np.multiply(venting, outside_water - humidity, out=change[1])
            np.multiply(venting, outside_co2 - co2, out=change[2])
            for axis, low, high, into_low, into_high in faces:
                difference = np.diff(carried, axis=axis)
                change[low] += into_low * difference
                change[high] -= into_high * difference
            carried += change
            if drying_any:
                # Equipment dries what the air then holds, never more.
                taken = np.minimum(drying, humidity)
                humidity -= taken
                removed += taken
            if step % condensing_every == 0 or step == steps:
                beyond = np.where(
                    solid, 0.0, np.maximum(humidity - saturation_ratio_g_kg(temperature), 0.0)
                )
                humidity -= beyond
                condensed += beyond
        return AirState(
            temperature=temperature.copy(),
            humidity=humidity.copy(),
            co2=co2.copy(),
            removed_kg=air.removed_kg + float(removed.sum()) * air_kg / GRAMS_PER_KG,
            condensed_kg=air.condensed_kg + float(condensed.sum()) * air_kg / GRAMS_PER_KG,
        )

    def water_kg(self, humidity: np.ndarray) -> float:
        """The water the air holds, in kilograms."""
        air_kg = AIR_DENSITY_KG_M3 * self.cell_volume_m3()
        return float(humidity[~self.solid].sum()) * air_kg / GRAMS_PER_KG

    def heat_j(self, temperature: np.ndarray, reference_c: float = 0.0) -> float:
        """The heat the air holds above `reference_c`, in joules."""
        air = ~self.solid
        excess = float((temperature[air] - reference_c).sum())
        return excess * AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K * self.cell_volume_m3()

    def envelope_loss_w(self, temperature: np.ndarray) -> float:
        """The heat the air loses through the walls and roof, in watts:
        negative when it gains it from a warmer outside."""
        exchange = self.exchange_m3_s() * AIR_DENSITY_KG_M3 * AIR_HEAT_CAPACITY_J_KG_K
        return float((exchange * (temperature - self.settings.outside_temperature_c)).sum())
