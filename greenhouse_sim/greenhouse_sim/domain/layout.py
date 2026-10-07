"""What a greenhouse's layout is made of: its fixtures, what they are made of
and stand in the way of, and what its zones are kept for."""

from enum import StrEnum


class ZoneKind(StrEnum):
    """What an area of the floor is kept for."""

    # Room for service: carts, harvest trolleys, irrigation and climate units.
    SERVICE = "service"
    # Where robots and trolleys must not go.
    KEEP_OUT = "keep_out"


class FixtureKind(StrEnum):
    """What a fixture is, for every consumer of its geometry."""

    # A trough the crop grows in, on stands or hung from the structure.
    CROP_GUTTER = "crop_gutter"
    # A bench or table that plants stand on, in pots or trays.
    BENCH = "bench"
    # Substrate the crop roots in, such as a stone wool or coir slab.
    SLAB = "slab"
    # A path on the floor, kept clear for people, trolleys and robots.
    WALKWAY = "walkway"
    # A rail that trolleys and robots run on.
    RAIL = "rail"
    # A pipe, such as a heating pipe.
    PIPE = "pipe"
    # A wire overhead, such as a crop wire the plants are trained up to.
    WIRE = "wire"
    # Anything else in the way: a column, a tank, a cabinet.
    OBSTACLE = "obstacle"


class Material(StrEnum):
    """What a fixture, or a part of the envelope, is made of."""

    STEEL = "steel"
    ALUMINIUM = "aluminium"
    PLASTIC = "plastic"
    CONCRETE = "concrete"
    # A growing medium, such as stone wool or coir.
    SUBSTRATE = "substrate"


class Obstruction(StrEnum):
    """What a fixture stands in the way of."""

    # Robots, trolleys and people cannot pass through it.
    MOVEMENT = "movement"
    # Air cannot flow through it.
    AIRFLOW = "airflow"
    # It casts a shadow.
    LIGHT = "light"
