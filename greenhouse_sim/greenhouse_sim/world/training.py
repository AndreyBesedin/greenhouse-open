"""How a crop is trained to its wires, and where a lowered stem lies (P09.3).

A high-wire crop hangs from its crop wires, and as it grows past them it is
lowered: a grower unwinds its twine, slides its hook along the wire, and lays
its bare lower stem down along the row. In a high-wire double row, two wires
hang above each run of a row's positions, `CropWires.offset` to either side
of it, and its plants are trained to them by turns: its first plant to the
wire on its left, its next to the one on its right, and so on.

The stems they lay down lie in a lane around the run (`Lane`), along either
edge of its support, as a carousel: a plant on the left wire lays its stem
forward along the run's left edge, one on the right wire back along its
right edge, and each passes round the run's end to the other edge when its
stem gets there, so that the stems lie side by side along the gutter, as
the plants beside them do. Where its laid stem ends, a plant's stem rises,
leaning out from the lane towards the wire above that edge, which it
reaches at the wire's height; round an end, towards a wire as far out.

Without a pair of wires, a plant's stem is laid straight along its row and
rises straight up (`AlongItsRow`).

A plant's path (`greenhouse_sim.biology.tomato.organ.geometry.StemPath`)
is given in its own frame: the greenhouse's, its foot at the origin.
"""

import math
from dataclasses import dataclass

from greenhouse_sim.biology.tomato.organ.geometry import StemPath
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.rows import CropRows, PlantingPosition
from greenhouse_sim.world.zones import Strip

_UP = Vector3(x=0.0, y=0.0, z=1.0)


def _plus(a: Vector3, b: Vector3, scale: float = 1.0) -> Vector3:
    return Vector3(x=a.x + b.x * scale, y=a.y + b.y * scale, z=a.z + b.z * scale)


def _minus(a: Vector3, b: Vector3) -> Vector3:
    return Vector3(x=a.x - b.x, y=a.y - b.y, z=a.z - b.z)


@dataclass(frozen=True)
class Lane:
    """A loop around a run's centre line from `start` to `end`, in the
    greenhouse's frame at the height the crop stands, `half_width` either
    side of it: forward along its left edge, round its far end, back along
    its right edge and round its near end; `left` is to the left of the way
    from `start` to `end`, seen from above."""

    start: Vector3
    end: Vector3
    half_width: float

    @property
    def straight_m(self) -> float:
        return math.dist((self.start.x, self.start.y), (self.end.x, self.end.y))

    @property
    def length_m(self) -> float:
        """Once round it."""
        return 2 * self.straight_m + 2 * math.pi * self.half_width

    @property
    def along(self) -> Vector3:
        length = self.straight_m
        return Vector3(
            x=(self.end.x - self.start.x) / length, y=(self.end.y - self.start.y) / length, z=0.0
        )

    @property
    def left(self) -> Vector3:
        along = self.along
        return Vector3(x=-along.y, y=along.x, z=0.0)

    def at(self, distance_m: float) -> tuple[Vector3, Vector3]:
        """The point `distance_m` round the lane from the start of its left
        edge, and the unit direction outward from the lane there, level."""
        straight, turn = self.straight_m, math.pi * self.half_width
        along, left = self.along, self.left
        s = distance_m % self.length_m
        if s <= straight:
            return _plus(_plus(self.start, left, self.half_width), along, s), left
        s -= straight
        if s <= turn:
            # Round the far end, from its left edge to its right.
            angle = math.pi / 2 - s / self.half_width
            return self._round(self.end, angle)
        s -= turn
        if s <= straight:
            right = _plus(self.end, left, -self.half_width)
            return _plus(right, along, -s), Vector3(x=-left.x, y=-left.y, z=0.0)
        s -= straight
        # Round the near end, from its right edge to its left.
        angle = -math.pi / 2 - s / self.half_width
        return self._round(self.start, angle)

    def _round(self, centre: Vector3, angle: float) -> tuple[Vector3, Vector3]:
        along, left = self.along, self.left
        outward = Vector3(
            x=along.x * math.cos(angle) + left.x * math.sin(angle),
            y=along.y * math.cos(angle) + left.y * math.sin(angle),
            z=0.0,
        )
        return _plus(centre, outward, self.half_width), outward

    def onto(self, point: Vector3, on_the_left: bool) -> float:
        """How far round the lane the point beside `point` on its left or
        right edge lies."""
        along = _minus(point, self.start).dot(self.along)
        if on_the_left:
            return along
        return self.straight_m + math.pi * self.half_width + (self.straight_m - along)


@dataclass(frozen=True)
class HighWire:
    """A plant of a high-wire double row, in its own frame: its foot at
    `foot` in the greenhouse's, its stem laid round `lane` from beside its
    foot on its left edge or its right, and rising towards a wire `offset`
    out from the run's centre line and `wire_m` above its foot."""

    lane: Lane
    foot: Vector3
    on_the_left: bool
    offset: float
    wire_m: float

    def laid(self, length_m: float) -> Vector3:
        start = self.lane.onto(self.foot, self.on_the_left)
        point, _ = self.lane.at(start + length_m)
        return _minus(point, self.foot)

    def rising(self, laid_m: float) -> Vector3:
        if laid_m == 0.0:
            # From its foot, on the centre line, out to its own wire.
            left = self.lane.left
            sideways = left if self.on_the_left else Vector3(x=-left.x, y=-left.y, z=0.0)
            out = self.offset
        else:
            start = self.lane.onto(self.foot, self.on_the_left)
            _, sideways = self.lane.at(start + laid_m)
            out = self.offset - self.lane.half_width
        return _plus(Vector3(x=0.0, y=0.0, z=self.wire_m), sideways, out).unit()


@dataclass(frozen=True)
class AlongItsRow:
    """A stem laid straight along its row, `along` in the greenhouse's
    frame, rising straight up."""

    along: Vector3

    def laid(self, length_m: float) -> Vector3:
        return Vector3(x=self.along.x * length_m, y=self.along.y * length_m, z=0.0)

    def rising(self, laid_m: float) -> Vector3:
        return _UP


@dataclass(frozen=True)
class Training:
    """How the plant at `position` is trained: the path its stem takes in
    its own frame, and how high above its foot the wire it hangs from is,
    if it hangs from one."""

    position: PlantingPosition
    path: StemPath
    wire_m: float | None = None


def trainings(rows: CropRows, kept_clear: list[Strip]) -> list[Training]:
    """How each of the rows' planting positions is trained, in their order:
    by turns to the left and right wires of a pair above its run, laying
    its stem round the run's lane; or else straight along its row."""
    positions = rows.planting_positions(kept_clear)
    wires = rows.wires
    if wires is None or wires.offset == 0.0:
        along = Vector3(x=rows.along.x, y=rows.along.y, z=0.0)
        wire = None if wires is None else wires.height - rows.planting_height
        return [Training(position=p, path=AlongItsRow(along), wire_m=wire) for p in positions]
    half_width = (
        wires.offset / 2 if rows.support is None else min(rows.support.width / 2, wires.offset / 2)
    )
    lanes = {
        (row, index): Lane(
            start=rows.point(row, start, z=rows.planting_height),
            end=rows.point(row, end, z=rows.planting_height),
            half_width=half_width,
        )
        for row in range(1, rows.rows + 1)
        for (first, last), start, end in rows.run_spans(row, kept_clear)
        for index in range(first, last + 1)
    }
    wire_m = wires.height - rows.planting_height
    return [
        Training(
            position=position,
            path=HighWire(
                lane=lanes[(position.row, position.index)],
                foot=position.point,
                on_the_left=position.index % 2 == 1,
                offset=wires.offset,
                wire_m=wire_m,
            ),
            wire_m=wire_m,
        )
        for position in positions
    ]
