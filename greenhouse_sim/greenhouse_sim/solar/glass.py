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
- **A described cover** (decision 0080, `world.components.Cover`): each
  surface passes its own sheet's share of a beam square to it, in place of
  single glass's 0.85, under the same modifier, ASHRAE's for glass, whatever
  the sheet. The diffuse sky passes each surface's sheet's own diffuse
  transmittance, for the share of the sky the floor sees through that
  surface: the roof's for the most of it, and a wall's for the low sky
  beyond it, which the floor near the wall sees the most of.
- **The floor's view of the sky** through each surface is summed over
  points on the floor and directions over the sky, each direction an equal
  share of a level surface's view of it, through the surface its ray leaves
  by. It is the house's as a whole: a point near a wall takes the same share
  of its sky through it as one at the house's middle, and a surface facing
  other than up the same as the floor.
"""

from dataclasses import dataclass
from typing import Final

import numpy as np

from greenhouse_sim.domain.envelope import SurfaceCategory
from greenhouse_sim.world.components import Cover
from greenhouse_sim.world.envelope import Envelope, Surface, outline
from greenhouse_sim.world.geometry import Vector3

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
# At most this many pairs of a point and an edge are worked out at once,
# 8 MB for each array of them: a large house's points go in batches.
PAIRS_AT_ONCE: Final = 1 << 20
# The directions the floor's view of the sky is summed over, each an equal
# share of a level surface's view of it: as many bands of equal sin² of
# their angle from the zenith, and as many azimuths in each.
SKY_BANDS: Final = 16
SKY_AZIMUTHS: Final = 48
# The points the floor's view of the sky is summed from: as many along each
# of its sides.
FLOOR_POINTS_ALONG: Final = 16
# Where in its part of the sky or the floor a direction or a point stands:
# at its middle.
MIDDLE: Final = 0.5


def transmittance(
    cos_incidence: np.ndarray, normal: float | np.ndarray = NORMAL_TRANSMITTANCE
) -> np.ndarray:
    """The share of a beam the glass passes, at each cosine of its incidence
    on the glass, for glass that passes `normal` of a beam square to it:
    single glass's, unless it is told another, for each cosine or all."""
    cosine = np.clip(cos_incidence, 0.0, 1.0)
    with np.errstate(divide="ignore"):
        modifier = 1.0 - INCIDENCE_COEFFICIENT * (1.0 / cosine - 1.0)
    return np.where(cosine > 0, normal * np.clip(modifier, 0.0, 1.0), 0.0)


def sky_directions() -> np.ndarray:
    """Directions over the sky, as rows of unit vectors (x, y, z), each an
    equal share of a level surface's view of it. That view between the
    zenith angles θ and θ + dθ is 2 sin θ cos θ dθ, the change in sin² θ, so
    bands of equal sin² θ hold equal shares (`SKY_BANDS`), each split
    evenly by azimuth (`SKY_AZIMUTHS`); a direction stands at the middle of
    its part."""
    sine_squared = (np.arange(SKY_BANDS) + MIDDLE) / SKY_BANDS
    azimuth = 2.0 * np.pi * (np.arange(SKY_AZIMUTHS) + MIDDLE) / SKY_AZIMUTHS
    sine = np.sqrt(sine_squared)[:, np.newaxis]
    up = np.sqrt(1.0 - sine_squared)[:, np.newaxis]
    east, north, zenith = np.broadcast_arrays(sine * np.cos(azimuth), sine * np.sin(azimuth), up)
    return np.stack([east, north, zenith], axis=-1).reshape(SKY_BANDS * SKY_AZIMUTHS, -1)


def floor_points(envelope: Envelope) -> np.ndarray:
    """Points over an envelope's floor, as rows of x, y, z in the world's
    axes: the middles of `FLOOR_POINTS_ALONG` by as many equal parts of the
    rectangle around its outline, those on the floor."""
    floor = next(
        surface
        for surface in envelope.surfaces_in_world()
        if surface.category == SurfaceCategory.FLOOR
    )
    corners = _outline(floor)
    low, high = corners.min(axis=0), corners.max(axis=0)
    parts = (np.arange(FLOOR_POINTS_ALONG) + MIDDLE) / FLOOR_POINTS_ALONG
    u, v = (
        grid.ravel()
        for grid in np.meshgrid(
            low[0] + parts * (high[0] - low[0]), low[1] + parts * (high[1] - low[1])
        )
    )
    on = _within(u, v, _Outline.of(corners))
    origin = _vector(floor.transform.position)
    across = _vector(floor.transform.rotation.rotate(Vector3(x=1.0, y=0.0, z=0.0)))
    up = _vector(floor.transform.rotation.rotate(Vector3(x=0.0, y=1.0, z=0.0)))
    points: np.ndarray = origin + u[on, np.newaxis] * across + v[on, np.newaxis] * up
    return points


def _outline(surface: Surface) -> np.ndarray:
    """A surface's outline in its own x-y plane (`outline`), as rows of
    points."""
    return np.array([[point.x, point.y] for point in outline(surface.shape)])


@dataclass(frozen=True)
class _Outline:
    """A polygon's edges, each from a corner to the next, as columns that
    broadcast against rows of points: the edges are tested all at once."""

    ax: np.ndarray
    ay: np.ndarray
    bx: np.ndarray
    by: np.ndarray
    # Each edge's length, squared.
    length_squared: np.ndarray

    @classmethod
    def of(cls, outline: np.ndarray) -> _Outline:
        following = np.roll(outline, -1, axis=0)
        # Each edge's length squared as a number on its own, so that it is
        # the very number a test of the edge alone would find.
        squared = [
            np.hypot(bx - ax, by - ay) ** 2
            for (ax, ay), (bx, by) in zip(outline, following, strict=True)
        ]

        def column(values: np.ndarray) -> np.ndarray:
            return np.asarray(values, dtype=float)[:, np.newaxis]

        return cls(
            ax=column(outline[:, 0]),
            ay=column(outline[:, 1]),
            bx=column(following[:, 0]),
            by=column(following[:, 1]),
            length_squared=column(np.array(squared)),
        )


def _within(u: np.ndarray, v: np.ndarray, outline: _Outline) -> np.ndarray:
    """Whether each point (u, v) lies inside a polygon, or within `SEAM_M`
    of its edges: in batches of points, each tested against every edge at
    once."""
    batch = max(1, PAIRS_AT_ONCE // len(outline.ax))
    within = np.empty(len(u), dtype=bool)
    for start in range(0, len(u), batch):
        part = slice(start, start + batch)
        within[part] = _within_batch(u[part], v[part], outline)
    return within


def _within_batch(u: np.ndarray, v: np.ndarray, outline: _Outline) -> np.ndarray:
    ax, ay, bx, by = outline.ax, outline.ay, outline.bx, outline.by
    crosses = (ay > v) != (by > v)
    with np.errstate(divide="ignore", invalid="ignore"):
        crossing = ax + (v - ay) * (bx - ax) / (by - ay)
    # A point is inside if a ray from it crosses the outline an odd number
    # of times.
    inside: np.ndarray = np.logical_xor.reduce(crosses & (u < crossing), axis=0)
    # How far each point lies from each edge.
    along = np.clip(
        ((u - ax) * (bx - ax) + (v - ay) * (by - ay)) / outline.length_squared, 0.0, 1.0
    )
    apart = np.hypot(u - (ax + along * (bx - ax)), v - (ay + along * (by - ay)))
    near = (apart <= SEAM_M).any(axis=0)
    within: np.ndarray = inside | near
    return within


@dataclass(frozen=True)
class _Pane:
    origin: np.ndarray
    across: np.ndarray
    up: np.ndarray
    # Facing into the house.
    normal: np.ndarray
    outline: _Outline
    # The share of a beam square to it that it passes, and of the sky's
    # diffuse light.
    normal_transmittance: float
    diffuse_transmittance: float


def _vector(vector: Vector3) -> np.ndarray:
    return np.array([vector.x, vector.y, vector.z])


class Glazing:
    """An envelope's walls and roof, as the sun's beam crosses them on its way
    to points inside, in the world's axes: single glass, unless its `cover`
    is described."""

    def __init__(self, envelope: Envelope, cover: Cover | None = None) -> None:
        self.panes = [
            _Pane(
                origin=_vector(surface.transform.position),
                across=_vector(surface.transform.rotation.rotate(Vector3(x=1.0, y=0.0, z=0.0))),
                up=_vector(surface.transform.rotation.rotate(Vector3(x=0.0, y=1.0, z=0.0))),
                normal=_vector(surface.transform.rotation.rotate(Vector3(x=0.0, y=0.0, z=1.0))),
                outline=_Outline.of(_outline(surface)),
                normal_transmittance=(
                    NORMAL_TRANSMITTANCE
                    if cover is None
                    else cover.sheet(surface.surface_id).shortwave_beam_transmittance
                ),
                diffuse_transmittance=(
                    DIFFUSE_TRANSMITTANCE
                    if cover is None
                    else cover.sheet(surface.surface_id).shortwave_diffuse_transmittance
                ),
            )
            for surface in envelope.surfaces_in_world()
            if surface.category in GLAZED
        ]
        self._beam_passes = np.array([pane.normal_transmittance for pane in self.panes])
        # What the diffuse sky passes on its way to the floor.
        self.diffuse_transmittance = (
            DIFFUSE_TRANSMITTANCE
            if cover is None
            else self._sky_passed(cover.sheet("roof").shortwave_diffuse_transmittance, envelope)
        )

    def _sky_passed(self, roof: float, envelope: Envelope) -> float:
        """What the diffuse sky passes on its way to the floor, the roof's
        sheet passing `roof` of it: each surface's sheet its own share of it
        for the share of the sky the floor sees through that surface. A cover
        of one diffuse transmittance passes that, as it is; a ray that leaves
        through no surface is taken through the roof."""
        differences = np.array([pane.diffuse_transmittance - roof for pane in self.panes])
        if not differences.any():
            return roof
        return roof + float(self.sky_shares(floor_points(envelope)) @ differences)

    def sky_shares(self, points: np.ndarray) -> np.ndarray:
        """The share of the sky a level surface at `points` (rows of x, y, z)
        inside sees through each of `panes`, in their order, over all the
        points: each of `sky_directions` an equal share of each point's view,
        through the pane its ray leaves by."""
        directions = sky_directions()
        # Every point's ray in every direction, at once.
        through, _ = self._leaving(
            np.repeat(points, len(directions), axis=0), np.tile(directions, (len(points), 1))
        )
        rays = np.bincount(through[through >= 0], minlength=len(self.panes))
        shares: np.ndarray = rays / len(through)
        return shares

    def cos_incidence(self, points: np.ndarray, towards: Vector3) -> np.ndarray:
        """The cosine of the angle the beam meets the glass at, for each of
        `points` (rows of x, y, z) inside, on its way from the sun in the
        unit direction `towards` it: at the surface the ray from the point
        towards the sun leaves through; nothing for a ray that leaves
        through none."""
        return self._crossed(points, towards)[0]

    def _crossed(self, points: np.ndarray, towards: Vector3) -> tuple[np.ndarray, np.ndarray]:
        """For each of `points`, the cosine the beam on its way to it meets
        the glass at (`cos_incidence`), and what that glass passes of a beam
        square to it."""
        through, cosine = self._leaving(points, _vector(towards))
        passes = np.where(through >= 0, self._beam_passes[through], NORMAL_TRANSMITTANCE)
        return cosine, passes

    def _leaving(self, points: np.ndarray, direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """For each of `points`, the pane the ray from it in the unit
        `direction`, one for all or a row for each, leaves the house
        through, by its place in `panes`, or −1 for none; and the cosine of
        the angle it meets that pane at."""
        count = len(points)
        nearest = np.full(count, np.inf)
        cosine = np.zeros(count)
        through = np.full(count, -1)
        for index, pane in enumerate(self.panes):
            facing = direction @ pane.normal
            # The rays that neither run along the pane nor come back into the
            # house through it.
            towards = facing < 0
            if not np.any(towards):
                continue
            distance = (pane.origin - points) @ pane.normal / np.where(towards, facing, -1.0)
            hit = points + distance[:, np.newaxis] * direction
            offset = hit - pane.origin
            leaves = (
                towards
                & (distance > 0)
                & _within(offset @ pane.across, offset @ pane.up, pane.outline)
            )
            nearer = leaves & (distance < nearest)
            nearest = np.where(nearer, distance, nearest)
            cosine = np.where(nearer, -facing, cosine)
            through = np.where(nearer, index, through)
        return through, cosine

    def beam_transmittance(self, points: np.ndarray, towards: Vector3) -> np.ndarray:
        """The share of the sun's beam, from the unit direction `towards` it,
        the glass passes on its way to each of `points` inside."""
        return transmittance(*self._crossed(points, towards))
