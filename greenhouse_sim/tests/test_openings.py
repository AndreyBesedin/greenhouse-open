"""Doors and vents: where they stand as they open, and the aperture each
exposes in the greenhouse's boundary."""

import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.world.envelope import Envelope, Opening
from greenhouse_sim.world.geometry import Point2, Vector3

HOUSE = Envelope(length=24.0, width=12.8, eave_height=5.5, ridge_height=7.9, spans=2, bays=4)
# A vent along the length near the first span's ridge, and a door on the front gable.
VENT = Opening(
    opening_id="roof_vent_1",
    kind=OpeningKind.ROOF_VENT,
    surface_id="roof_1_right",
    centre=Point2(x=0.0, y=1.0),
    width=4.0,
    height=1.0,
)
DOOR = Opening(
    opening_id="door_1",
    kind=OpeningKind.DOOR,
    surface_id="end_wall_front",
    centre=Point2(x=2.0, y=1.1),
    width=1.5,
    height=2.2,
)


def _with(*openings: Opening) -> Envelope:
    return Envelope.model_validate(HOUSE.model_dump() | {"openings": list(openings)})


def _opened(opening: Opening, fraction: float) -> Opening:
    return opening.model_copy(update={"opening": fraction})


def test_a_closed_opening_exposes_no_aperture() -> None:
    assert VENT.aperture_area() == 0.0
    assert DOOR.aperture_area() == 0.0


def test_a_door_opens_its_fraction_of_its_area() -> None:
    assert _opened(DOOR, 0.5).aperture_area() == pytest.approx(0.5 * 1.5 * 2.2)
    assert _opened(DOOR, 1.0).aperture_area() == pytest.approx(1.5 * 2.2)


def test_a_vent_opens_a_curtain_at_its_free_edge_and_sides() -> None:
    """At a quarter of 45 degrees: the free edge's gap, 4 m long and as wide as
    the chord its edge swings through, plus a triangle at each side."""
    angle = math.radians(45) / 4
    expected = 4.0 * 2 * 1.0 * math.sin(angle / 2) + 1.0**2 * math.sin(angle)

    assert _opened(VENT, 0.25).aperture_area() == pytest.approx(expected)


def test_a_wide_open_vent_exposes_no_more_than_its_frame() -> None:
    """A long, shallow vent's curtain stays under its frame even wide open; a
    deep one's would pass it, and its frame is all it opens."""
    wide_open = math.radians(45)
    long_and_shallow = _opened(VENT, 1.0)
    deep = _opened(VENT.model_copy(update={"width": 2.0}), 1.0)

    assert long_and_shallow.aperture_area() == pytest.approx(
        4.0 * 2 * math.sin(wide_open / 2) + math.sin(wide_open)
    )
    assert long_and_shallow.aperture_area() < 4.0 * 1.0
    assert deep.aperture_area() == pytest.approx(2.0 * 1.0)


def test_a_vent_exposes_more_the_further_it_opens() -> None:
    areas = [_opened(VENT, fraction / 10).aperture_area() for fraction in range(11)]

    assert areas == sorted(areas)
    assert areas[0] == 0.0 < areas[1]


@pytest.mark.parametrize(
    ("opening", "message"),
    [
        (VENT.model_copy(update={"surface_id": "roof_9_left"}), "not a surface"),
        (VENT.model_copy(update={"centre": Point2(x=11.5, y=1.0)}), "does not fit"),
        (DOOR.model_copy(update={"height": 9.0}), "does not fit"),
    ],
)
def test_an_opening_must_fit_on_a_surface_of_the_envelope(opening: Opening, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _with(opening)


def test_every_opening_needs_its_own_identifier() -> None:
    with pytest.raises(ValidationError, match="its own identifier"):
        _with(VENT, VENT.model_copy(update={"surface_id": "roof_2_right"}))


def test_an_opening_opens_from_closed_to_fully_and_no_further() -> None:
    for fraction in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            Opening.model_validate(VENT.model_dump() | {"opening": fraction})


def _panel_corners(envelope: Envelope) -> list[Vector3]:
    [panel] = envelope.opening_panels()
    half_x, half_y = panel.shape.size_x / 2, panel.shape.size_y / 2
    return [
        panel.transform.apply(Vector3(x=x, y=y, z=0.0))
        for x, y in [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]
    ]


def _host_distance(envelope: Envelope, surface_id: str, point: Vector3) -> float:
    """How far a point lies in front of a surface (into the house), in metres."""
    host = next(s for s in envelope.surfaces() if s.surface_id == surface_id)
    normal = host.transform.rotation.rotate(Vector3(x=0, y=0, z=1))
    origin = host.transform.position
    return (
        normal.x * (point.x - origin.x)
        + normal.y * (point.y - origin.y)
        + normal.z * (point.z - origin.z)
    )


def test_a_closed_vent_lies_on_its_roof_slope() -> None:
    envelope = _with(VENT)

    for corner in _panel_corners(envelope):
        assert _host_distance(envelope, "roof_1_right", corner) == pytest.approx(0.0, abs=1e-12)


def test_an_open_vent_swings_outward_about_its_upper_edge() -> None:
    closed = _panel_corners(_with(VENT))
    angle = math.radians(45) / 2
    envelope = _with(_opened(VENT, 0.5))
    opened = _panel_corners(envelope)

    # The upper edge, its hinge, stays put; the lower edge swings out of the
    # house by the panel's height times the sine of its angle.
    for upper in (2, 3):
        assert (opened[upper].x, opened[upper].y, opened[upper].z) == pytest.approx(
            (closed[upper].x, closed[upper].y, closed[upper].z)
        )
    for lower in (0, 1):
        reach = _host_distance(envelope, "roof_1_right", opened[lower])
        assert reach == pytest.approx(-1.0 * math.sin(angle))


def test_a_door_slides_along_its_wall_just_outside_it() -> None:
    closed = _panel_corners(_with(DOOR))
    envelope = _with(_opened(DOOR, 1.0))
    opened = _panel_corners(envelope)

    shift = [opened[i].y - closed[i].y for i in range(4)]
    assert shift == pytest.approx([1.5] * 4)
    for corner in opened:
        assert _host_distance(envelope, "end_wall_front", corner) < 0


def test_the_api_opens_a_scenarios_vent_and_refuses_what_cannot_open() -> None:
    def vent(query: str) -> dict[str, str | int | float | bool]:
        response = respond("GET", f"/api/scenarios/climate_box/scene{query}")
        scene = SceneSnapshot.model_validate(response.body)
        [entity] = [e for e in scene.entities if e.entity_id == "climate_box_roof_vent"]
        return entity.properties

    # Shut to start. Wide open, at 45°, the 4 by 1 m vent's curtain: the gap
    # along its free edge and the two triangles at its sides.
    widest = math.radians(45)
    curtain = 4.0 * 2 * 1.0 * math.sin(widest / 2) + 1.0**2 * math.sin(widest)
    assert vent("")["open_fraction"] == 0.0
    assert vent("?open=roof_vent:1")["open_fraction"] == 1.0
    assert vent("?open=roof_vent:1")["aperture_m2"] == pytest.approx(curtain)
    for query in ["?open=roof_vent:2", "?open=nope:1", "?open=roof_vent:wide"]:
        response = respond("GET", f"/api/scenarios/climate_box/scene{query}")
        assert response.status == 400
        assert isinstance(response.body, dict) and response.body["error"]
