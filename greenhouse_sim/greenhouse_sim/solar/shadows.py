"""What shades the sun's beam inside the greenhouse (P08.5, P08.6).

- **What casts shadows:** the greenhouse's structure, its posts and rafters
  (round bars) and its gutters (channels, `world.envelope`), every fixture
  of its layout that obstructs light (`Obstruction.LIGHT`): crop gutters,
  benches, slabs, rails, pipes and obstacles; and its plants' crowns
  (`solar.plants`). Equipment obstructs no light, and casts none.
- **How:** a point is in the beam's shadow if the ray from it towards the
  sun meets any of them on its way: exact ray tests against each box (by
  its slabs) and each finite cylinder (its side and its ends), in each
  one's own frame, vectorised over many points at once. A point inside a
  solid is in its shadow.
- **The diffuse sky** is shaded by the structure as a whole (P08.7): by
  the share of the house's plan its rafters and gutters cover, seen from
  above (`roof_shading`), the same everywhere inside. What stands inside,
  fixtures and crowns, shades the diffuse sky not at all.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

from greenhouse_sim.domain.layout import Obstruction
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Box, Cylinder, Transform, Vector3
from greenhouse_sim.world.layout import Layout

# How many solids are tested against all the points at once, which bounds
# the arrays a test makes.
BATCH: Final = 64
# Below this, a ray runs along a cylinder's axis, or a box's face.
PARALLEL: Final = 1e-12

type Solid = tuple[Transform, Box | Cylinder]


def _axes(transform: Transform) -> np.ndarray:
    """A frame's own x, y and z axes, in its parent's axes, as rows."""
    rotation = transform.rotation
    return np.array(
        [
            [axis.x, axis.y, axis.z]
            for axis in (
                rotation.rotate(Vector3(x=1.0, y=0.0, z=0.0)),
                rotation.rotate(Vector3(x=0.0, y=1.0, z=0.0)),
                rotation.rotate(Vector3(x=0.0, y=0.0, z=1.0)),
            )
        ]
    )


def _position(transform: Transform) -> np.ndarray:
    return np.array([transform.position.x, transform.position.y, transform.position.z])


@dataclass(frozen=True, eq=False)
class _Boxes:
    # Each box's frame: its base's middle, and its own axes as rows.
    origins: np.ndarray
    axes: np.ndarray
    # Its half sizes along its own x and y, and its height up its z.
    halves: np.ndarray
    heights: np.ndarray

    def meet(self, points: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """Whether the ray from each point along `direction` meets any box."""
        met = np.zeros(len(points), dtype=bool)
        for start in range(0, len(self.origins), BATCH):
            chunk = slice(start, start + BATCH)
            axes = self.axes[chunk]
            # Each point, and the ray's direction, in each box's own frame.
            local = np.einsum("bij,bnj->bni", axes, points[np.newaxis] - self.origins[chunk, None])
            heading = np.einsum("bij,j->bi", axes, direction)[:, None, :]
            low = np.stack(
                [-self.halves[chunk, 0], -self.halves[chunk, 1], np.zeros(len(axes))], axis=1
            )[:, None, :]
            high = np.stack(
                [self.halves[chunk, 0], self.halves[chunk, 1], self.heights[chunk]], axis=1
            )[:, None, :]
            along = np.abs(heading) > PARALLEL
            safe = np.where(along, heading, 1.0)
            first = np.where(along, (low - local) / safe, -np.inf)
            second = np.where(along, (high - local) / safe, np.inf)
            # A ray square to an axis stays within that slab, or never enters.
            within = (local >= low) & (local <= high)
            enter = np.where(along, np.minimum(first, second), np.where(within, -np.inf, np.inf))
            leave = np.where(along, np.maximum(first, second), np.where(within, np.inf, -np.inf))
            nearest = enter.max(axis=2)
            farthest = leave.min(axis=2)
            met |= ((farthest >= nearest) & (farthest > 0)).any(axis=0)
        return met


@dataclass(frozen=True, eq=False)
class _Cylinders:
    # Each cylinder's frame: its base's middle, and its own axes as rows, its
    # z along its axis.
    origins: np.ndarray
    axes: np.ndarray
    radii: np.ndarray
    heights: np.ndarray

    def meet(self, points: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """Whether the ray from each point along `direction` meets any
        cylinder."""
        met = np.zeros(len(points), dtype=bool)
        for start in range(0, len(self.origins), BATCH):
            chunk = slice(start, start + BATCH)
            axes = self.axes[chunk]
            local = np.einsum("bij,bnj->bni", axes, points[np.newaxis] - self.origins[chunk, None])
            heading = np.einsum("bij,j->bi", axes, direction)
            radii = self.radii[chunk, None]
            heights = self.heights[chunk, None]
            x, y, z = local[..., 0], local[..., 1], local[..., 2]
            dx, dy, dz = heading[:, 0:1], heading[:, 1:2], heading[:, 2:3]
            # Its side: where the ray's distance from the axis is the radius,
            # a t² + 2 h t + c = 0, its roots (−h ± √(h² − a c)) / a.
            a = dx**2 + dy**2
            h = x * dx + y * dy
            c = x**2 + y**2 - radii**2
            sideways = a > PARALLEL
            safe_a = np.where(sideways, a, 1.0)
            disc = h**2 - safe_a * c
            root = np.sqrt(np.maximum(disc, 0.0))
            side_in = np.where(sideways, (-h - root) / safe_a, -np.inf)
            side_out = np.where(sideways, (-h + root) / safe_a, np.inf)
            # Along the axis, it stays inside the side or never meets it.
            side_misses = np.where(sideways, disc < 0, c > 0)
            # Its ends: where the ray is between its base and its top.
            upright = np.abs(dz) > PARALLEL
            safe_dz = np.where(upright, dz, 1.0)
            first = (0.0 - z) / safe_dz
            second = (heights - z) / safe_dz
            between = (z >= 0) & (z <= heights)
            end_in = np.where(
                upright, np.minimum(first, second), np.where(between, -np.inf, np.inf)
            )
            end_out = np.where(
                upright, np.maximum(first, second), np.where(between, np.inf, -np.inf)
            )
            nearest = np.maximum(side_in, end_in)
            farthest = np.minimum(side_out, end_out)
            met |= (~side_misses & (farthest >= nearest) & (farthest > 0)).any(axis=0)
        return met


def _boxes(solids: Sequence[tuple[Transform, Box]]) -> _Boxes:
    return _Boxes(
        origins=np.array([_position(t) for t, _ in solids]).reshape(-1, 3),
        axes=np.array([_axes(t) for t, _ in solids]).reshape(-1, 3, 3),
        halves=np.array([[b.size_x / 2, b.size_y / 2] for _, b in solids]).reshape(-1, 2),
        heights=np.array([b.size_z for _, b in solids]),
    )


def _cylinders(solids: Sequence[tuple[Transform, Cylinder]]) -> _Cylinders:
    return _Cylinders(
        origins=np.array([_position(t) for t, _ in solids]).reshape(-1, 3),
        axes=np.array([_axes(t) for t, _ in solids]).reshape(-1, 3, 3),
        radii=np.array([c.radius for _, c in solids]),
        heights=np.array([c.height for _, c in solids]),
    )


class Shadows:
    """The solids that shade the sun's beam, each placed in the world."""

    def __init__(self, solids: Iterable[Solid]) -> None:
        boxes: list[tuple[Transform, Box]] = []
        cylinders: list[tuple[Transform, Cylinder]] = []
        for transform, shape in solids:
            if isinstance(shape, Box):
                boxes.append((transform, shape))
            else:
                cylinders.append((transform, shape))
        self._boxes = _boxes(boxes)
        self._cylinders = _cylinders(cylinders)
        self.count = len(boxes) + len(cylinders)

    @classmethod
    def of(cls, envelope: Envelope, layout: Layout, more: Iterable[Solid] = ()) -> Shadows:
        """What shades the beam in a greenhouse: its structure, and its
        layout's fixtures that obstruct light; and `more`, such as its
        plants' crowns (`solar.plants`), already placed in the world."""
        placed: list[Solid] = [
            *(gutter.solid() for gutter in envelope.gutters()),
            *(member.solid() for member in envelope.members()),
            *(
                (fixture.transform, fixture.shape)
                for fixture in layout.obstructing(Obstruction.LIGHT)
            ),
        ]
        return cls(
            [
                *((envelope.origin.after(transform), shape) for transform, shape in placed),
                *more,
            ]
        )

    def lit(self, points: np.ndarray, towards: Vector3) -> np.ndarray:
        """Whether the sun's beam, from the unit direction `towards` it,
        reaches each of `points` (rows of x, y, z) unshaded."""
        direction = np.array([towards.x, towards.y, towards.z])
        shaded = np.zeros(len(points), dtype=bool)
        if len(self._boxes.origins):
            shaded |= self._boxes.meet(points, direction)
        if len(self._cylinders.origins):
            shaded |= self._cylinders.meet(points, direction)
        return ~shaded


def roof_shading(envelope: Envelope) -> float:
    """The share of a house's plan its roof's structure covers, seen from
    above: each rafter's width along its run across the span, and each
    gutter's width, as far as it lies over the house, along its length. The
    posts, upright, cover next to nothing."""
    low_y, high_y = 0.0, envelope.width
    covered = 0.0
    for member in envelope.members():
        _, bar = member.solid()
        run = math.hypot(member.end.x - member.start.x, member.end.y - member.start.y)
        covered += 2 * bar.radius * run
    for gutter in envelope.gutters():
        _, channel = gutter.solid()
        y = gutter.start.y
        inside = min(y + channel.size_y / 2, high_y) - max(y - channel.size_y / 2, low_y)
        covered += max(inside, 0.0) * channel.size_x
    return covered / (envelope.length * envelope.width)
