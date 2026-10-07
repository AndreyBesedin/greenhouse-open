"""What the parts of a greenhouse's envelope are: its surfaces, its
structural members and its openings."""

from enum import StrEnum


class SurfaceCategory(StrEnum):
    """What a surface of the envelope is, for every consumer of its geometry."""

    FLOOR = "floor"
    WALL = "wall"
    ROOF = "roof"


class MemberKind(StrEnum):
    """What a structural member is."""

    POST = "post"
    RAFTER = "rafter"


class OpeningKind(StrEnum):
    DOOR = "door"
    ROOF_VENT = "roof_vent"
    SIDE_VENT = "side_vent"
