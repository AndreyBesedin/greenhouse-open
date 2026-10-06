"""Areas of the floor kept for a purpose: walkways, service zones and
keep-out volumes, and how other parts of the layout keep clear of them.

Each is a strip of the floor: a centre line from `start` to `end`, `width`
wide, in the greenhouse's frame. A service zone or keep-out volume rises
`height` above it. No planting position lies inside a walkway, a service
zone or a keep-out volume, and nothing that obstructs movement stands on a
walkway, so walkways stay clear.
"""

import math
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, PositiveFloat, model_validator

from greenhouse_sim.world.geometry import Point2, Vector3

# Things that only touch an area's edge are not inside it: a tenth of a
# millimetre, well below any building tolerance.
EDGE_TOLERANCE_M: Final = 0.0001


class Strip(BaseModel):
    """A rectangle of the floor: a centre line from `start` to `end`, `width`
    wide."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: Point2
    end: Point2
    width: PositiveFloat

    @model_validator(mode="after")
    def _has_a_length(self) -> Self:
        if self.start == self.end:
            raise ValueError("its start and end are the same point")
        return self

    @property
    def length(self) -> float:
        return math.hypot(self.end.x - self.start.x, self.end.y - self.start.y)

    @property
    def middle(self) -> Point2:
        return Point2(x=(self.start.x + self.end.x) / 2, y=(self.start.y + self.end.y) / 2)

    @property
    def heading(self) -> float:
        """The centre line's direction, as a turn from the greenhouse's x."""
        return math.atan2(self.end.y - self.start.y, self.end.x - self.start.x)

    def _local(self, x: float, y: float) -> tuple[float, float]:
        """A floor point in the strip's own terms: along its centre line from
        its middle, and across it, to its left."""
        heading, middle = self.heading, self.middle
        dx, dy = x - middle.x, y - middle.y
        along = dx * math.cos(heading) + dy * math.sin(heading)
        across = -dx * math.sin(heading) + dy * math.cos(heading)
        return along, across

    def corners(self) -> list[Point2]:
        """The strip's four corners on the floor."""
        heading, middle = self.heading, self.middle
        along = Point2(x=math.cos(heading), y=math.sin(heading))
        across = Point2(x=-along.y, y=along.x)
        return [
            Point2(
                x=middle.x + along.x * a * self.length / 2 + across.x * c * self.width / 2,
                y=middle.y + along.y * a * self.length / 2 + across.y * c * self.width / 2,
            )
            for a, c in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]

    def contains(self, point: Point2 | Vector3, margin: float = 0.0) -> bool:
        """Whether a point lies inside the strip, widened by `margin` on every
        side, seen from above; one on its edge does not."""
        along, across = self._local(point.x, point.y)
        return (
            abs(along) < self.length / 2 + margin - EDGE_TOLERANCE_M
            and abs(across) < self.width / 2 + margin - EDGE_TOLERANCE_M
        )

    def overlaps(self, corners: list[Vector3]) -> bool:
        """Whether the box around some corners, seen from above and squared to
        the strip, reaches inside it. Things square to the strip, as fixtures
        along rows and aisles are, are judged exactly; others cautiously."""
        local = [self._local(corner.x, corner.y) for corner in corners]
        alongs, acrosses = [a for a, _ in local], [c for _, c in local]
        half_length = self.length / 2 - EDGE_TOLERANCE_M
        half_width = self.width / 2 - EDGE_TOLERANCE_M
        return (
            min(alongs) < half_length
            and max(alongs) > -half_length
            and min(acrosses) < half_width
            and max(acrosses) > -half_width
        )

    def crossing(
        self, start: Point2, direction: Point2, half_width: float
    ) -> tuple[float, float] | None:
        """Where a band `half_width` either side of the line from `start`
        along the unit `direction`, such as a support laid along a row,
        reaches into the strip: the distances along the line between which it
        does, or None if it never does."""
        along_start, across_start = self._local(start.x, start.y)
        heading = self.heading
        along_step = direction.x * math.cos(heading) + direction.y * math.sin(heading)
        across_step = -direction.x * math.sin(heading) + direction.y * math.cos(heading)
        # The band's edge reaches as far as its half-width, square to its line,
        # does along each of the strip's axes.
        low, high = -math.inf, math.inf
        for offset, step, half in (
            (along_start, along_step, self.length / 2 + abs(across_step) * half_width),
            (across_start, across_step, self.width / 2 + abs(along_step) * half_width),
        ):
            if step == 0.0:
                if abs(offset) >= half:
                    return None
                continue
            first, second = (-half - offset) / step, (half - offset) / step
            low, high = max(low, min(first, second)), min(high, max(first, second))
        return (low, high) if low < high else None


class ZoneKind(StrEnum):
    """What an area of the floor is kept for."""

    # Room for service: carts, harvest trolleys, irrigation and climate units.
    SERVICE = "service"
    # Where robots and trolleys must not go.
    KEEP_OUT = "keep_out"


class Zone(BaseModel):
    """A service zone or keep-out volume: a strip of the floor, rising
    `height` above it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    zone_id: str
    kind: ZoneKind
    area: Strip
    height: PositiveFloat
