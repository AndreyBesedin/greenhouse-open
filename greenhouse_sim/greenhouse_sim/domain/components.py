"""What a house's described components are (P24.2, decision 0080): its
screens, its pipe networks, and what a house air model may or may not
model of them."""

from enum import StrEnum


class ScreenKind(StrEnum):
    """What a screen drawn across the house is for."""

    # Keeps the house's heat in, at night.
    THERMAL = "thermal"
    # Takes some of the sun's light off the crop.
    SHADING = "shading"
    # Keeps the light of the lamps in, or the day out.
    BLACKOUT = "blackout"


class PipeKind(StrEnum):
    """Where a network of heating pipes runs."""

    # On the floor, between the rows, as the rails trolleys run on.
    RAIL = "rail"
    # Up in the crop.
    GROW = "grow"
    # Along the walls.
    PERIMETER = "perimeter"


class Component(StrEnum):
    """A component a house describes, as a house air model models it or
    refuses the house: its cover's materials, a wall on a neighbouring
    space or on nothing, its floor, a screen, a pipe network."""

    COVER = "cover"
    WALL_ON_A_SPACE = "wall_on_a_space"
    WALL_ON_NOTHING = "wall_on_nothing"
    FLOOR = "floor"
    SCREEN = "screen"
    PIPE_NETWORK = "pipe_network"
