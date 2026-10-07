"""Prescribed airflow: known patterns of flow, set by a few numbers.

Three patterns, each a function of position over the grid's box (its width
along y, its height along z):

- **uniform:** one breeze everywhere, at one temperature.
- **buoyancy:** convection, as warm air over a warm middle makes it. Air
  rises up the middle of the house and sinks along its side walls, in two
  rolls side by side, over air that warms with height and towards the
  middle.
- **vortex:** one roll across the house, turning about its length, as a
  draught along the roof might drive, at one temperature.

The rolls follow stream functions in the y-z plane, ψ = A sin(m π y/W)
sin(π z/H) for m rolls. So they are divergence-free, as moving air is, and
never flow through the box's walls, floor or roof.
"""

import math
from typing import Annotated, Final, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat

from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, EnvironmentField, FieldGrid
from greenhouse_sim.world.geometry import Vector3

# Rolls across the box: one for a vortex, two side by side for convection.
VORTEX_ROLLS: Final = 1
CONVECTION_ROLLS: Final = 2


class UniformAirflow(BaseModel):
    """One breeze everywhere, at one temperature."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["uniform"] = "uniform"
    velocity_m_s: Vector3 = Vector3(x=0.3, y=0.0, z=0.0)
    temperature_c: float = 20.0

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        z, _, _ = _coordinates(grid)
        velocity = np.zeros((*z.shape, VECTOR_COMPONENTS))
        velocity[...] = (self.velocity_m_s.x, self.velocity_m_s.y, self.velocity_m_s.z)
        return EnvironmentField(
            field_id=field_id,
            source="prescribed:uniform",
            grid=grid,
            time_s=time_s,
            channels={
                AirQuantity.VELOCITY: velocity,
                AirQuantity.TEMPERATURE: np.full(z.shape, self.temperature_c),
            },
        )


class BuoyancyAirflow(BaseModel):
    """Convection: air rising up the middle and sinking along the side walls,
    over air warming with height and towards the middle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["buoyancy"] = "buoyancy"
    # The fastest the air moves anywhere.
    peak_speed_m_s: NonNegativeFloat = 0.25
    # The air's temperature at the floor and under the roof, at the side walls.
    floor_temperature_c: float = 18.0
    ceiling_temperature_c: float = 23.0
    # How much warmer the middle is than the side walls.
    middle_warming_c: NonNegativeFloat = 1.5

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        z, y, _ = _coordinates(grid)
        across, up = _shares(grid, y, z)
        velocity = _rolls(grid, across, up, CONVECTION_ROLLS, self.peak_speed_m_s)
        temperature = (
            self.floor_temperature_c
            + (self.ceiling_temperature_c - self.floor_temperature_c) * up
            + self.middle_warming_c * (1 - np.cos(2 * math.pi * across)) / 2
        )
        return EnvironmentField(
            field_id=field_id,
            source="prescribed:buoyancy",
            grid=grid,
            time_s=time_s,
            channels={AirQuantity.VELOCITY: velocity, AirQuantity.TEMPERATURE: temperature},
        )


class VortexAirflow(BaseModel):
    """One roll across the house, turning about its length."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["vortex"] = "vortex"
    peak_speed_m_s: NonNegativeFloat = 0.5
    temperature_c: float = 20.0

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        z, y, _ = _coordinates(grid)
        across, up = _shares(grid, y, z)
        return EnvironmentField(
            field_id=field_id,
            source="prescribed:vortex",
            grid=grid,
            time_s=time_s,
            channels={
                AirQuantity.VELOCITY: _rolls(grid, across, up, VORTEX_ROLLS, self.peak_speed_m_s),
                AirQuantity.TEMPERATURE: np.full(z.shape, self.temperature_c),
            },
        )


# A scenario's airflow: one of the prescribed patterns, with its numbers.
type PrescribedAirflow = Annotated[
    UniformAirflow | BuoyancyAirflow | VortexAirflow, Field(discriminator="kind")
]

# Each pattern by name, as its typical numbers set it.
PATTERNS: Final[dict[str, UniformAirflow | BuoyancyAirflow | VortexAirflow]] = {
    "uniform": UniformAirflow(),
    "buoyancy": BuoyancyAirflow(),
    "vortex": VortexAirflow(),
}


def _coordinates(grid: FieldGrid) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The cells' centres' z, y and x, each an array of the field's shape."""
    xs, ys, zs = grid.centres()
    z, y, x = np.meshgrid(zs, ys, xs, indexing="ij")
    return z, y, x


def _shares(grid: FieldGrid, y: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """How far across the box's width, and up its height, each point is, from
    0 to 1."""
    top = grid.maximum
    across = (y - grid.origin.y) / (top.y - grid.origin.y)
    up = (z - grid.origin.z) / (top.z - grid.origin.z)
    return across, up


def _rolls(
    grid: FieldGrid, across: np.ndarray, up: np.ndarray, rolls: int, peak: float
) -> np.ndarray:
    """The velocity of `rolls` rolls side by side across the box, turning
    about its length, from the stream function ψ = A sin(rolls π a) sin(π u)
    over a box W wide and H high, scaled so the fastest air moves at `peak`."""
    width = grid.maximum.y - grid.origin.y
    height = grid.maximum.z - grid.origin.z
    across_rate = rolls * math.pi / width
    up_rate = math.pi / height
    amplitude = peak / max(up_rate, across_rate)
    velocity = np.zeros((*across.shape, VECTOR_COMPONENTS))
    # v = ∂ψ/∂z and w = -∂ψ/∂y.
    velocity[..., 1] = amplitude * up_rate * np.sin(rolls * math.pi * across) * np.cos(math.pi * up)
    velocity[..., 2] = (
        -amplitude * across_rate * np.cos(rolls * math.pi * across) * np.sin(math.pi * up)
    )
    return velocity
