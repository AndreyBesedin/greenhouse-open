"""A fan's jet: what a running fan adds to the air's velocity (P05.2).

A fan blows a round free jet along its heading. Its rotor gives the air a
core speed, U₀, its flow over the area it sweeps. At a distance x from the
rotor, along its axis:

- **across it,** the speed falls off as a Gaussian of the distance r from
  its axis, u = U(x) exp(−(r / b(x))²);
- **its core:** for K rotor diameters D, the jet keeps the rotor's radius R
  as its width and its core speed on its axis, U(x) = U₀;
- **beyond,** it widens linearly, b(x) = x / (2K), and slows as it widens,
  so that its momentum is kept: U(x) b(x) = U₀ R, or U(x) = K U₀ D / x, the
  classic decay of a round jet, with K = 6.

So the air through a plane across the jet is the fan's flow, π R² U₀, over
its core, and grows beyond it as the jet entrains the air around it. The
jet blows along its axis only, and adds nothing behind the rotor, in the
cells obstacles fill, or beyond a few widths from its axis. A fan at a level
blows that share of its flow.

The jet is added to the air's base flow without making their sum
divergence-free (a known approximation of P05).
"""

import math
from typing import Final

import numpy as np

from greenhouse_sim.fields.field import VECTOR_COMPONENTS, FieldGrid
from greenhouse_sim.world.equipment import Fan

# The decay constant of a round free jet: beyond its core, this many nozzle
# diameters long, its speed on its axis is this many nozzle diameters over
# the distance, times its core speed.
JET_DECAY: Final = 6.0
# How far from its axis the jet reaches, in widths: beyond, it adds less than
# a ten-thousandth of its speed on the axis.
JET_REACH_WIDTHS: Final = 3.0


def jet_velocity(fan: Fan, level: float, grid: FieldGrid, solid: np.ndarray) -> np.ndarray:
    """The velocity a fan's jet adds at a level, at every cell's centre of a
    grid whose `solid` cells obstacles fill, in the grid's order (z, y, x)
    with its three components last."""
    xs, ys, zs = grid.centres()
    z, y, x = np.meshgrid(zs, ys, xs, indexing="ij")
    axis = fan.facing()
    dx, dy, dz = x - fan.position.x, y - fan.position.y, z - fan.position.z
    along = dx * axis.x + dy * axis.y + dz * axis.z
    across_squared = np.maximum(dx**2 + dy**2 + dz**2 - along**2, 0.0)
    radius = fan.diameter_m / 2
    width = np.maximum(radius, along / (2 * JET_DECAY))
    core_speed = level * fan.flow_m3_s / (math.pi * radius**2)
    reached = (along >= 0.0) & (across_squared <= (JET_REACH_WIDTHS * width) ** 2) & ~solid
    speed = np.where(reached, core_speed * radius / width * np.exp(-across_squared / width**2), 0.0)
    velocity = np.zeros((*speed.shape, VECTOR_COMPONENTS))
    velocity[...] = (axis.x, axis.y, axis.z)
    result: np.ndarray = velocity * speed[..., None]
    return result
