"""The sun's light through the greenhouse's glass (P08.4).

- **Transmission:** glass passes a share τ of the beam that reaches it: its
  normal-incidence transmittance, 0.85 for single glass, times an
  incidence-angle modifier after ASHRAE, 1 − b₀ (1 / cos θ − 1), b₀ = 0.1,
  θ the angle between the beam and the glass's normal, never below
  nothing. The glass passes less as the sun grazes it, and nothing beyond
  about 85°.
- **The diffuse sky's** transmittance is the modifier's mean over the
  hemisphere, weighted by the cosine the light falls at,
  2 ∫ τ(θ) cos θ sin θ dθ, which is τₙ ((1 + b₀)(1 − c₀²) − 2 b₀ (1 − c₀)),
  c₀ = b₀ / (1 + b₀) the cosine below which the modifier is nothing: about
  0.773 for single glass.
- **Which surface:** the beam reaching a point inside crosses the envelope
  where the ray from the point towards the sun leaves it, a wall or a roof
  slope, at that surface's own angle. Each surface is the envelope's flat
  polygon (`world.envelope`), facing in; a ray leaves through the nearest
  one it meets. A ray leaving one span's roof towards another's is taken
  through the glass once only: low winter beams across a multi-span roof
  are passed a little too much.
- **Openings:** an open vent's or door's aperture passes the beam as glass
  does, for now.
"""

from dataclasses import dataclass
from typing import Final

import numpy as np

from greenhouse_sim.domain.envelope import SurfaceCategory
from greenhouse_sim.world.envelope import Envelope, Surface
from greenhouse_sim.world.geometry import Point2, Vector3

# Single glass's transmittance square to the beam, and ASHRAE's
# incidence-angle coefficient for glass.
NORMAL_TRANSMITTANCE: Final = 0.85
INCIDENCE_COEFFICIENT: Final = 0.1
# The cosine of incidence below which the glass passes nothing.
LEAST_COSINE: Final = INCIDENCE_COEFFICIENT / (1.0 + INCIDENCE_COEFFICIENT)
DIFFUSE_TRANSMITTANCE: Final = NORMAL_TRANSMITTANCE * (
    (1.0 + INCIDENCE_COEFFICIENT) * (1.0 - LEAST_COSINE**2)
    - 2.0 * INCIDENCE_COEFFICIENT * (1.0 - LEAST_COSINE)
)
# How far outside its outline, in metres, a ray may meet a surface and still
# leave through it: the seams between surfaces are shared.
SEAM_M: Final = 1e-6
# The surfaces light leaves the house through.
GLAZED: Final = frozenset({SurfaceCategory.WALL, SurfaceCategory.ROOF})


def transmittance(cos_incidence: np.ndarray) -> np.ndarray:
    """The share of a beam the glass passes, at each cosine of its incidence
    on the glass."""
    cosine = np.clip(cos_incidence, 0.0, 1.0)
    with np.errstate(divide="ignore"):
        modifier = 1.0 - INCIDENCE_COEFFICIENT * (1.0 / cosine - 1.0)
    return np.where(cosine > 0, NORMAL_TRANSMITTANCE * np.clip(modifier, 0.0, 1.0), 0.0)


def _outline(surface: Surface) -> np.ndarray:
    """A surface's outline in its own x-y plane, as rows of points."""
    shape = surface.shape
    if shape.shape == "polygon":
        points: list[Point2] = shape.points
        return np.array([[point.x, point.y] for point in points])
    half_x, half_y = shape.size_x / 2, shape.size_y / 2
    return np.array([[-half_x, -half_y], [half_x, -half_y], [half_x, half_y], [-half_x, half_y]])


def _within(u: np.ndarray, v: np.ndarray, outline: np.ndarray) -> np.ndarray:
    """Whether each point (u, v) lies inside a polygon, or within `SEAM_M`
    of its edges."""
    inside = np.zeros(u.shape, dtype=bool)
    near = np.zeros(u.shape, dtype=bool)
    count = len(outline)
    for index in range(count):
        (ax, ay), (bx, by) = outline[index], outline[(index + 1) % count]
        crosses = (ay > v) != (by > v)
        with np.errstate(divide="ignore", invalid="ignore"):
            crossing = ax + (v - ay) * (bx - ax) / (by - ay)
        inside ^= crosses & (u < crossing)
        # How far each point lies from this edge.
        edge = np.hypot(bx - ax, by - ay)
        along = np.clip(((u - ax) * (bx - ax) + (v - ay) * (by - ay)) / edge**2, 0.0, 1.0)
        near |= np.hypot(u - (ax + along * (bx - ax)), v - (ay + along * (by - ay))) <= SEAM_M
    return inside | near


@dataclass(frozen=True)
class _Pane:
    origin: np.ndarray
    across: np.ndarray
    up: np.ndarray
    # Facing into the house.
    normal: np.ndarray
    outline: np.ndarray


def _vector(vector: Vector3) -> np.ndarray:
    return np.array([vector.x, vector.y, vector.z])


class Glazing:
    """An envelope's walls and roof, as the sun's beam crosses them on its way
    to points inside, in the world's axes."""

    def __init__(self, envelope: Envelope) -> None:
        self.panes = [
            _Pane(
                origin=_vector(surface.transform.position),
                across=_vector(surface.transform.rotation.rotate(Vector3(x=1.0, y=0.0, z=0.0))),
                up=_vector(surface.transform.rotation.rotate(Vector3(x=0.0, y=1.0, z=0.0))),
                normal=_vector(surface.transform.rotation.rotate(Vector3(x=0.0, y=0.0, z=1.0))),
                outline=_outline(surface),
            )
            for surface in envelope.surfaces_in_world()
            if surface.category in GLAZED
        ]

    def cos_incidence(self, points: np.ndarray, towards: Vector3) -> np.ndarray:
        """The cosine of the angle the beam meets the glass at, for each of
        `points` (rows of x, y, z) inside, on its way from the sun in the
        unit direction `towards` it: at the surface the ray from the point
        towards the sun leaves through; nothing for a ray that leaves
        through none."""
        direction = _vector(towards)
        count = len(points)
        nearest = np.full(count, np.inf)
        cosine = np.zeros(count)
        for pane in self.panes:
            facing = float(direction @ pane.normal)
            if facing >= 0:
                # The ray runs along it, or back into the house through it.
                continue
            distance = (pane.origin - points) @ pane.normal / facing
            hit = points + distance[:, np.newaxis] * direction
            offset = hit - pane.origin
            leaves = (distance > 0) & _within(offset @ pane.across, offset @ pane.up, pane.outline)
            nearer = leaves & (distance < nearest)
            nearest = np.where(nearer, distance, nearest)
            cosine = np.where(nearer, -facing, cosine)
        return cosine

    def beam_transmittance(self, points: np.ndarray, towards: Vector3) -> np.ndarray:
        """The share of the sun's beam, from the unit direction `towards` it,
        the glass passes on its way to each of `points` inside."""
        return transmittance(self.cos_incidence(points, towards))
