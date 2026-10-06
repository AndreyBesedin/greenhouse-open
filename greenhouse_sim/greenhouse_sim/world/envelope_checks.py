"""Checks on a greenhouse's generated envelope: its surfaces' outlines and
edges, whether each faces into the house (decision 0017), whether together
they close it, and whether a point lies inside the space they enclose. Tests
hold every envelope to these; P04 can check its own boundary with them."""

from typing import Final

from greenhouse_sim.world.envelope import Envelope, Surface
from greenhouse_sim.world.geometry import Vector3

type Point = tuple[float, float, float]

# Corners are compared to the micrometre: far finer than any building
# tolerance, far coarser than floating-point noise.
MICROMETRE_DECIMALS: Final = 6
# How far in front of a surface its front is probed: a millimetre, well inside
# any greenhouse, well beyond rounding.
PROBE_M: Final = 0.001


def rounded(point: Vector3) -> Point:
    """A point rounded to a micrometre, so that corners can be compared."""
    return (
        round(point.x, MICROMETRE_DECIMALS),
        round(point.y, MICROMETRE_DECIMALS),
        round(point.z, MICROMETRE_DECIMALS),
    )


def outline(surface: Surface) -> list[Point]:
    """A surface's corners in order, in the greenhouse's frame."""
    shape = surface.shape
    if shape.shape == "plane":
        half_x, half_y = shape.size_x / 2, shape.size_y / 2
        corners = [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]
    else:
        corners = [(point.x, point.y) for point in shape.points]
    return [rounded(surface.transform.apply(Vector3(x=x, y=y, z=0.0))) for x, y in corners]


def edges(surface: Surface) -> set[frozenset[Point]]:
    """A surface's edges, each as the pair of corners it joins."""
    corners = outline(surface)
    return {frozenset((corners[i], corners[(i + 1) % len(corners)])) for i in range(len(corners))}


def shared_edges(envelope: Envelope) -> dict[frozenset[Point], int]:
    """How many surfaces share each edge."""
    shared: dict[frozenset[Point], int] = {}
    for surface in envelope.surfaces():
        for edge in edges(surface):
            shared[edge] = shared.get(edge, 0) + 1
    return shared


def roof_height(envelope: Envelope, y: float) -> float:
    """How high the roof stands at `y` across the width: at each ridge, its
    ridge height, falling to the eaves at each span's edges."""
    span_width = envelope.span_width
    span = min(int(y // span_width), envelope.spans - 1)
    ridge_y = span_width * span + span_width / 2
    rise = envelope.ridge_height - envelope.eave_height
    return envelope.ridge_height - rise * abs(y - ridge_y) / (span_width / 2)


def encloses(envelope: Envelope, point: Point) -> bool:
    """Whether a point of the greenhouse's frame lies inside the space its
    envelope encloses, or on its boundary."""
    x, y, z = point
    tolerance = PROBE_M / 2
    return (
        -tolerance <= x <= envelope.length + tolerance
        and -tolerance <= y <= envelope.width + tolerance
        and -tolerance <= z <= roof_height(envelope, min(max(y, 0.0), envelope.width)) + tolerance
    )


def inverted_surfaces(envelope: Envelope) -> list[str]:
    """The surfaces whose front does not face into the house: a point just in
    front of each one's centre must lie inside the space the envelope encloses."""
    inverted = []
    for surface in envelope.surfaces():
        facing = surface.transform.rotation.rotate(Vector3(x=0, y=0, z=1))
        corners = outline(surface)
        cx, cy, cz = (
            sum(corner[axis] for corner in corners) / len(corners)
            for axis in range(len(corners[0]))
        )
        in_front = (cx + facing.x * PROBE_M, cy + facing.y * PROBE_M, cz + facing.z * PROBE_M)
        if not encloses(envelope, in_front):
            inverted.append(surface.surface_id)
    return inverted
