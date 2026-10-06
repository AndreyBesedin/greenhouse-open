"""The greenhouse's envelope: where the greenhouse stands, and the space it encloses.

The greenhouse has a frame of its own (decision 0016). Its origin is a corner of
the floor; x runs along the greenhouse's length, y across its width, and z up,
so the greenhouse fills the positive octant of its frame. `origin` places that
frame in the world, by default at the world's origin, unrotated. Everything the
envelope describes is given in the greenhouse's frame, and `to_world` places it.

The envelope is a description, not geometry: its surfaces are generated from
it, for viewers now and for physics and airflow later, so a scenario, or later
an editor, changes the greenhouse by changing this description. P01 grows it
from the enclosed space to the floor, walls, roof, bays and openings.

Each surface is flat, faces into the greenhouse (decision 0017), and carries a
semantic category. Walls are named as seen from the greenhouse's origin,
looking along its length (+x): the right side wall stands along y = 0, the
left along y = width, the front end wall at x = 0 and the back at x = length.

The width is divided into spans, side by side, each with a pitched roof of its
own: two slopes meeting at a ridge along the length, above the middle of the
span. The side walls rise to the eaves, and the end walls are gables, with a
peak for each span. Gutters run along both eaves and along each valley between
spans. Spans are numbered from the right side wall (y = 0), starting at 1.

The length is divided into bays. A structural frame stands at each end of
every bay: a post at every gutter line, from the floor to the eaves, and a
rafter up each roof slope. Frames are numbered from the front end wall (x = 0),
starting at 0, and each is placed at its own multiple of the bay spacing, so
nothing drifts along the house.

Openings are rectangles on a host surface, given in the host's own x-y plane,
with an open fraction from 0 (closed) to 1. Vents are top-hung: hinged along
their upper edge, they swing outward, up to their largest angle. Doors slide
sideways, just outside their wall. Each opening exposes an aperture in the
boundary: what airflow will pass through (P04). The host's surface is not cut:
an opening lies on it.
"""

import math
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

from greenhouse_sim.world.geometry import Plane, Point2, Polygon, Quaternion, Transform, Vector3

# Where a greenhouse stands unless a scenario says otherwise: its floor corner
# at the world's origin, its axes along the world's.
AT_WORLD_ORIGIN = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))
# How far a vent swings open unless it says otherwise: 45 degrees, typical of
# roof vents on glasshouses.
DEFAULT_LARGEST_VENT_ANGLE_RAD = math.radians(45)
# A door slides this far outside its wall, so that the two never touch.
DOOR_CLEARANCE_M = 0.02

_ALONG = Vector3(x=1.0, y=0.0, z=0.0)
_BACK_ALONG = Vector3(x=-1.0, y=0.0, z=0.0)
_ACROSS = Vector3(x=0.0, y=1.0, z=0.0)
_BACK_ACROSS = Vector3(x=0.0, y=-1.0, z=0.0)
_UP = Vector3(x=0.0, y=0.0, z=1.0)


class SurfaceCategory(StrEnum):
    """What a surface of the envelope is, for every consumer of its geometry."""

    FLOOR = "floor"
    WALL = "wall"
    ROOF = "roof"


class Surface(BaseModel):
    """One flat piece of the envelope, placed in the greenhouse's frame, with
    its front (its shape's +z) facing into the greenhouse."""

    model_config = ConfigDict(frozen=True)

    surface_id: str
    category: SurfaceCategory
    transform: Transform
    shape: Plane | Polygon


class Gutter(BaseModel):
    """A gutter's line, from end to end, in the greenhouse's frame."""

    model_config = ConfigDict(frozen=True)

    gutter_id: str
    start: Vector3
    end: Vector3


class MemberKind(StrEnum):
    """What a structural member is."""

    POST = "post"
    RAFTER = "rafter"


class OpeningKind(StrEnum):
    DOOR = "door"
    ROOF_VENT = "roof_vent"
    SIDE_VENT = "side_vent"


class Opening(BaseModel):
    """A door or vent: a rectangle on its host surface, centred at `centre` in
    the host's own x-y plane, `width` along the host's x and `height` along
    its y, open by `opening`, from 0 (closed) to 1."""

    model_config = ConfigDict(frozen=True)

    opening_id: str
    kind: OpeningKind
    surface_id: str
    centre: Point2
    width: PositiveFloat
    height: PositiveFloat
    opening: float = Field(default=0.0, ge=0.0, le=1.0)
    # How far a vent swings when fully open, in radians; doors slide instead.
    largest_angle: float = Field(default=DEFAULT_LARGEST_VENT_ANGLE_RAD, gt=0.0, le=math.pi / 2)

    def corners(self) -> list[Point2]:
        """The rectangle's corners in the host's x-y plane, when closed."""
        half_width, half_height = self.width / 2, self.height / 2
        x, y = self.centre.x, self.centre.y
        return [
            Point2(x=x - half_width, y=y - half_height),
            Point2(x=x + half_width, y=y - half_height),
            Point2(x=x + half_width, y=y + half_height),
            Point2(x=x - half_width, y=y + half_height),
        ]

    @property
    def angle(self) -> float:
        """How far a vent has swung open, in radians."""
        return self.opening * self.largest_angle if self.kind != OpeningKind.DOOR else 0.0

    def aperture_area(self) -> float:
        """The open area through the boundary, in square metres.

        A door slid open by a fraction opens that fraction of itself. A
        top-hung vent opens a "curtain": the gap at its free edge plus the two
        triangles at its sides, but never more than its own frame.
        """
        frame = self.width * self.height
        if self.kind == OpeningKind.DOOR:
            return self.opening * frame
        free_edge = self.width * 2 * self.height * math.sin(self.angle / 2)
        sides = self.height**2 * math.sin(self.angle)
        return min(frame, free_edge + sides)


class OpeningPanel(BaseModel):
    """Where an opening's panel stands as it is open, in the greenhouse's frame:
    a rectangle, centred on its transform's origin, facing into the house."""

    model_config = ConfigDict(frozen=True)

    opening: Opening
    transform: Transform
    shape: Plane


def _inside(point: Point2, polygon: list[Point2]) -> bool:
    """Whether a point lies inside a polygon or on its edge."""
    inside = False
    count = len(polygon)
    for index in range(count):
        a, b = polygon[index], polygon[(index + 1) % count]
        cross = (b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x)
        within_x = min(a.x, b.x) <= point.x <= max(a.x, b.x)
        within_y = min(a.y, b.y) <= point.y <= max(a.y, b.y)
        if math.isclose(cross, 0.0, abs_tol=1e-9) and within_x and within_y:
            return True
        if (a.y > point.y) != (b.y > point.y):
            crossing_x = a.x + (point.y - a.y) * (b.x - a.x) / (b.y - a.y)
            if point.x < crossing_x:
                inside = not inside
    return inside


def _outline(shape: Plane | Polygon) -> list[Point2]:
    """A host shape's outline in its own x-y plane."""
    if shape.shape == "polygon":
        return shape.points
    half_x, half_y = shape.size_x / 2, shape.size_y / 2
    return [
        Point2(x=-half_x, y=-half_y),
        Point2(x=half_x, y=-half_y),
        Point2(x=half_x, y=half_y),
        Point2(x=-half_x, y=half_y),
    ]


class Member(BaseModel):
    """A structural member's line, from its foot to its head, in the
    greenhouse's frame."""

    model_config = ConfigDict(frozen=True)

    member_id: str
    kind: MemberKind
    frame: int
    start: Vector3
    end: Vector3


def _surface(
    surface_id: str,
    category: SurfaceCategory,
    origin: Vector3,
    axes: tuple[Vector3, Vector3],
    shape: Plane | Polygon,
) -> Surface:
    """A surface whose own x and y axes lie along `axes`; its front faces their
    cross product."""
    return Surface(
        surface_id=surface_id,
        category=category,
        transform=Transform(position=origin, rotation=Quaternion.from_axes(*axes)),
        shape=shape,
    )


class Envelope(BaseModel):
    """A greenhouse's envelope, in metres."""

    model_config = ConfigDict(frozen=True)

    # Along the greenhouse's x.
    length: PositiveFloat
    # Along the greenhouse's y, across all its spans.
    width: PositiveFloat
    # From the floor to the eaves, where the walls and gutters meet the roof.
    eave_height: PositiveFloat
    # From the floor to each span's ridge, the roof's highest line. A ridge as
    # high as the eaves makes a flat roof.
    ridge_height: PositiveFloat
    # Spans side by side across the width, each as wide as the others.
    spans: PositiveInt = 1
    # Bays one after another along the length, each as long as the others.
    bays: PositiveInt = 1
    # Doors and vents, each on one of the envelope's surfaces.
    openings: list[Opening] = []
    # Places the greenhouse's frame in the world.
    origin: Transform = AT_WORLD_ORIGIN

    @model_validator(mode="after")
    def _ridge_is_not_below_the_eaves(self) -> Self:
        if self.ridge_height < self.eave_height:
            raise ValueError(
                f"the ridge ({self.ridge_height} m) is below the eaves ({self.eave_height} m)"
            )
        return self

    @model_validator(mode="after")
    def _openings_fit_their_surfaces(self) -> Self:
        hosts = {surface.surface_id: surface for surface in self.surfaces()}
        names = [opening.opening_id for opening in self.openings]
        if len(set(names)) != len(names):
            raise ValueError("every opening needs its own identifier")
        for opening in self.openings:
            host = hosts.get(opening.surface_id)
            if host is None:
                raise ValueError(
                    f"{opening.opening_id} is on {opening.surface_id!r}, not a surface"
                )
            outline = _outline(host.shape)
            if not all(_inside(corner, outline) for corner in opening.corners()):
                raise ValueError(f"{opening.opening_id} does not fit on {opening.surface_id}")
        return self

    @property
    def span_width(self) -> float:
        return self.width / self.spans

    @property
    def bay_spacing(self) -> float:
        return self.length / self.bays

    @property
    def roof_pitch(self) -> float:
        """The roof's slope from the eaves to the ridge, in radians."""
        return math.atan2(self.ridge_height - self.eave_height, self.span_width / 2)

    def bounds(self) -> tuple[Vector3, Vector3]:
        """The enclosed space's opposite corners, in the greenhouse's frame."""
        return (
            Vector3(x=0.0, y=0.0, z=0.0),
            Vector3(x=self.length, y=self.width, z=self.ridge_height),
        )

    def to_world(self, point: Vector3) -> Vector3:
        """Where a point given in the greenhouse's frame lies in the world."""
        return self.origin.apply(point)

    def _span_edge(self, index: int) -> float:
        """Where span `index` (counted from 0) starts across the width. Each
        edge is its own multiple of the span width, so none drifts."""
        return self.width * index / self.spans

    def _frame_position(self, frame: int) -> float:
        """Where frame `frame` stands along the length, as its own multiple."""
        return self.length * frame / self.bays

    def surfaces(self) -> list[Surface]:
        """The floor, the four walls and two roof slopes per span, in the
        greenhouse's frame. Together they close the greenhouse."""
        length, width = self.length, self.width
        eave, ridge = self.eave_height, self.ridge_height
        half_span = self.span_width / 2
        rise = ridge - eave
        slope = math.hypot(half_span, rise)
        # The end walls' gable, from its bottom corner along the width, up the
        # far side, then back over each span's peak and the valleys between.
        tops = [Point2(x=width, y=eave)]
        for index in reversed(range(self.spans)):
            tops.append(Point2(x=self._span_edge(index) + half_span, y=ridge))
            tops.append(Point2(x=self._span_edge(index), y=eave))
        gable = Polygon(points=[Point2(x=0.0, y=0.0), Point2(x=width, y=0.0), *tops])
        side = Plane(size_x=length, size_y=eave)
        roof = Plane(size_x=length, size_y=slope)
        # Up each roof slope, from its eave to the ridge.
        up_right_slope = Vector3(x=0.0, y=half_span / slope, z=rise / slope)
        up_left_slope = Vector3(x=0.0, y=-half_span / slope, z=rise / slope)
        mid_slope = (eave + ridge) / 2
        wall = SurfaceCategory.WALL
        surfaces = [
            _surface(
                "floor",
                SurfaceCategory.FLOOR,
                Vector3(x=length / 2, y=width / 2, z=0.0),
                (_ALONG, _ACROSS),
                Plane(size_x=length, size_y=width),
            ),
            _surface(
                "side_wall_right",
                wall,
                Vector3(x=length / 2, y=0.0, z=eave / 2),
                (_BACK_ALONG, _UP),
                side,
            ),
            _surface(
                "side_wall_left",
                wall,
                Vector3(x=length / 2, y=width, z=eave / 2),
                (_ALONG, _UP),
                side,
            ),
            _surface("end_wall_front", wall, Vector3(x=0.0, y=0.0, z=0.0), (_ACROSS, _UP), gable),
            _surface(
                "end_wall_back",
                wall,
                Vector3(x=length, y=width, z=0.0),
                (_BACK_ACROSS, _UP),
                gable,
            ),
        ]
        for index in range(self.spans):
            span_start = self._span_edge(index)
            number = index + 1
            surfaces += [
                _surface(
                    f"roof_{number}_right",
                    SurfaceCategory.ROOF,
                    Vector3(x=length / 2, y=span_start + half_span / 2, z=mid_slope),
                    (_BACK_ALONG, up_right_slope),
                    roof,
                ),
                _surface(
                    f"roof_{number}_left",
                    SurfaceCategory.ROOF,
                    Vector3(
                        x=length / 2, y=span_start + self.span_width - half_span / 2, z=mid_slope
                    ),
                    (_ALONG, up_left_slope),
                    roof,
                ),
            ]
        return surfaces

    def surfaces_in_world(self) -> list[Surface]:
        """The same surfaces, placed in the world by the greenhouse's origin."""
        return [
            surface.model_copy(update={"transform": self.origin.after(surface.transform)})
            for surface in self.surfaces()
        ]

    def opening_panels(self) -> list[OpeningPanel]:
        """Each opening's panel as it stands open, in the greenhouse's frame. A
        vent turns about its upper edge, outward; a door slides along its wall,
        just outside it."""
        hosts = {surface.surface_id: surface for surface in self.surfaces()}
        panels = []
        for opening in self.openings:
            host = hosts[opening.surface_id]
            half_height = opening.height / 2
            if opening.kind == OpeningKind.DOOR:
                # Slid along the host's x by its open fraction, outside the wall.
                in_host = Transform(
                    position=Vector3(
                        x=opening.centre.x + opening.opening * opening.width,
                        y=opening.centre.y,
                        z=-DOOR_CLEARANCE_M,
                    )
                )
            else:
                # Turned about the hinge at its upper edge: a turn about the
                # host's x swings the lower edge to the host's -z, outward.
                turn = Quaternion.about(Vector3(x=1.0, y=0.0, z=0.0), opening.angle)
                hinge = Vector3(x=opening.centre.x, y=opening.centre.y + half_height, z=0.0)
                down_the_panel = turn.rotate(Vector3(x=0.0, y=-half_height, z=0.0))
                in_host = Transform(
                    position=Vector3(
                        x=hinge.x + down_the_panel.x,
                        y=hinge.y + down_the_panel.y,
                        z=hinge.z + down_the_panel.z,
                    ),
                    rotation=turn,
                )
            panels.append(
                OpeningPanel(
                    opening=opening,
                    transform=host.transform.after(in_host),
                    shape=Plane(size_x=opening.width, size_y=opening.height),
                )
            )
        return panels

    def gutters(self) -> list[Gutter]:
        """A gutter along each eave and each valley, the length of the
        greenhouse, numbered from the right side wall starting at 0."""
        eave = self.eave_height
        return [
            Gutter(
                gutter_id=f"gutter_{index}",
                start=Vector3(x=0.0, y=self._span_edge(index), z=eave),
                end=Vector3(x=self.length, y=self._span_edge(index), z=eave),
            )
            for index in range(self.spans + 1)
        ]

    def members(self) -> list[Member]:
        """The structural frames: at every bay line, a post at every gutter
        line and a rafter up each roof slope, from the eaves to the ridge."""
        eave, ridge = self.eave_height, self.ridge_height
        half_span = self.span_width / 2
        members: list[Member] = []
        for frame in range(self.bays + 1):
            x = self._frame_position(frame)
            for index in range(self.spans + 1):
                y = self._span_edge(index)
                members.append(
                    Member(
                        member_id=f"frame_{frame}_post_{index}",
                        kind=MemberKind.POST,
                        frame=frame,
                        start=Vector3(x=x, y=y, z=0.0),
                        end=Vector3(x=x, y=y, z=eave),
                    )
                )
            for index in range(self.spans):
                span_start = self._span_edge(index)
                ridge_point = Vector3(x=x, y=span_start + half_span, z=ridge)
                for side, foot in (("right", span_start), ("left", self._span_edge(index + 1))):
                    members.append(
                        Member(
                            member_id=f"frame_{frame}_rafter_{index + 1}_{side}",
                            kind=MemberKind.RAFTER,
                            frame=frame,
                            start=Vector3(x=x, y=foot, z=eave),
                            end=ridge_point,
                        )
                    )
        return members
