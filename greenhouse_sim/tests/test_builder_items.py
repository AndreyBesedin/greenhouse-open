"""Equipment, sensors, doors and vents placed, copied, spaced, changed and
removed many at a time, and what the assessment says of items that collide
(P12.3)."""

import math

import pytest
from greenhouse_protocol.sensor import CameraIntrinsics
from pydantic import ValidationError

from greenhouse_sim.builder.basic import BasicSetup, basic_installation
from greenhouse_sim.builder.installation import assess_installation
from greenhouse_sim.builder.items import (
    MOST_AT_ONCE,
    place_items,
    place_openings,
    remove_items,
    repeat_items,
    repeat_openings,
    set_field,
    space_items,
    space_openings,
    spread_openings,
)
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.world.envelope import Opening
from greenhouse_sim.world.equipment import Fan, Heater
from greenhouse_sim.world.fixtures import WalkwayPrimitive
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.sensors import Camera, PointSensor

# Along the right wall, clear of the rows at y 2.2 and 3.8.
HEATER = Heater(
    actuator_id="heater",
    base=Vector3(x=1.0, y=0.6, z=0.0),
    size_x=0.6,
    size_y=0.6,
    size_z=1.0,
    power_w=10_000.0,
)
FAN = Fan(actuator_id="fan", position=Vector3(x=1.0, y=3.0, z=3.0), diameter_m=0.5, flow_m3_s=1.0)
SENSOR = PointSensor(
    sensor_id="temperature_back", kind=SensorKind.TEMPERATURE, position=Vector3(x=6, y=3, z=1.5)
)
CAMERA = Camera(
    sensor_id="camera",
    position=Vector3(x=0.5, y=3.0, z=2.0),
    target=Vector3(x=6.0, y=3.0, z=1.0),
    intrinsics=CameraIntrinsics(width=640, height=480, fx=500, fy=500, ppx=320, ppy=240),
)
VENT = Opening(
    opening_id="vent",
    kind=OpeningKind.ROOF_VENT,
    surface_id="roof_1_right",
    # Midway up a slope of the test house, 1.58 m from eave to ridge.
    centre=Point2(x=-4.0, y=0.0),
    width=1.0,
    height=0.6,
)


def _house(**changes: object) -> Installation:
    """A 12 m by 6 m house of two spans, its two rows along it at y 2.2 and
    3.8, with no equipment, sensors, doors or vents."""
    values = {
        "installation_id": "my_greenhouse",
        "name": "Test house",
        "length_m": 12.0,
        "width_m": 6.0,
        "eave_height_m": 4.0,
        "ridge_height_m": 4.5,
        "spans": 2,
        "bays": 3,
        "rows": 2,
        "plants_per_row": 6,
        "plant_pitch_m": 0.75,
        "row_spacing_m": 1.6,
        "support_height_m": 0.6,
        "crop_model": "organ",
        "variety": "cherry_tomato",
    }
    return basic_installation(BasicSetup.model_validate(values | changes))


def _ids(draft: Installation) -> list[str]:
    layout = draft.layout
    return [
        *(piece.actuator_id for piece in layout.equipment),
        *(sensor.sensor_id for sensor in layout.sensors),
        *(opening.opening_id for opening in draft.envelope.openings),
    ]


def _heaters(draft: Installation) -> list[Heater]:
    return [piece for piece in draft.layout.equipment if isinstance(piece, Heater)]


def _codes(draft: Installation) -> set[str]:
    return {finding.code for finding in assess_installation(draft)}


def test_many_pieces_are_placed_at_a_step_and_named_after_the_first() -> None:
    house = _house()

    placed = place_items(house, HEATER, count=3, step=Vector3(x=2.0, y=0.0, z=0.0))

    assert _ids(placed) == ["heater_1", "heater_2", "heater_3"]
    assert [piece.base.x for piece in _heaters(placed)] == [1.0, 3.0, 5.0]
    # The draft it was made from is as it was, for an undo.
    assert house.layout.equipment == []
    # The same edit of the same draft names its items the same.
    assert place_items(house, HEATER, count=3, step=Vector3(x=2.0, y=0.0, z=0.0)) == placed


def test_new_items_take_the_lowest_numbers_no_item_has() -> None:
    house = place_items(_house(), HEATER.model_copy(update={"actuator_id": "heater_2"}))

    again = place_items(house, HEATER, count=2, step=Vector3(x=0.0, y=0.0, z=2.0))

    assert _ids(again) == ["heater_1", "heater_2", "heater_3"]


@pytest.mark.parametrize(
    ("count", "step", "said"),
    [
        (0, Vector3(x=1.0, y=0.0, z=0.0), "from 1 to"),
        (MOST_AT_ONCE + 1, Vector3(x=0.01, y=0.0, z=0.0), "from 1 to"),
        (2, None, "give a step"),
    ],
)
def test_a_count_none_can_have_or_items_on_one_spot_are_refused(
    count: int, step: Vector3 | None, said: str
) -> None:
    with pytest.raises(ValueError, match=said):
        place_items(_house(), HEATER, count=count, step=step)


def test_what_the_layout_refuses_refuses_the_edit_with_its_reason() -> None:
    walkway = WalkwayPrimitive(
        fixture_id="path", start=Point2(x=0.0, y=0.6), end=Point2(x=12.0, y=0.6), width=1.0
    )
    house = _house()
    house = house.model_copy(
        update={"layout": house.layout.model_copy(update={"placed": [walkway]})}
    )

    with pytest.raises(ValidationError, match="heater_1 stands on the walkway path"):
        place_items(house, HEATER)


def test_chosen_items_are_copied_at_a_step_each_after_its_own_name() -> None:
    house = place_items(place_items(_house(), SENSOR), CAMERA)

    copied = repeat_items(
        house, ["temperature_back_1", "camera_1"], count=2, step=Vector3(x=1.0, y=0.0, z=0.5)
    )

    assert _ids(copied) == [
        "temperature_back_1",
        "camera_1",
        "temperature_back_2",
        "temperature_back_3",
        "camera_2",
        "camera_3",
    ]
    cameras = [s for s in copied.layout.sensors if isinstance(s, Camera)]
    # A camera's target moves with it: it looks the same way.
    assert [(c.position.x, c.target.x, c.target.z) for c in cameras] == [
        (0.5, 6.0, 1.0),
        (1.5, 7.0, 1.5),
        (2.5, 8.0, 2.0),
    ]


def test_copying_nothing_or_what_the_draft_has_not_is_refused() -> None:
    house = place_items(_house(), FAN)
    step = Vector3(x=1.0, y=0.0, z=0.0)

    with pytest.raises(ValueError, match="choose at least one item"):
        repeat_items(house, [], count=1, step=step)
    with pytest.raises(ValueError, match="no equipment or sensor heater_9"):
        repeat_items(house, ["fan_1", "heater_9"], count=1, step=step)
    with pytest.raises(ValueError, match="give a step"):
        repeat_items(house, ["fan_1"], count=2, step=Vector3(x=0.0, y=0.0, z=0.0))


def test_items_are_spaced_evenly_between_the_two_furthest_apart() -> None:
    house = _house()
    for x in (1.0, 2.0, 2.5, 9.0):
        house = place_items(house, HEATER.model_copy(update={"base": Vector3(x=x, y=0.6, z=0)}))

    spaced = space_items(house, ["heater_1", "heater_2", "heater_3", "heater_4"], axis="x")

    assert [(p.base.x, p.base.y) for p in _heaters(spaced)] == [
        (1.0, 0.6),
        (pytest.approx(11 / 3), 0.6),
        (pytest.approx(19 / 3), 0.6),
        (9.0, 0.6),
    ]
    with pytest.raises(ValueError, match="at least three"):
        space_items(house, ["heater_1", "heater_2"], axis="x")


def test_vents_are_placed_on_each_chosen_roof_slope_at_a_step() -> None:
    placed = place_openings(
        _house(), VENT, ["roof_1_right", "roof_2_left"], count=3, step=Point2(x=2.0, y=0.0)
    )

    by_surface = [(o.opening_id, o.surface_id, o.centre.x) for o in placed.envelope.openings]
    assert by_surface == [
        ("vent_1", "roof_1_right", -4.0),
        ("vent_2", "roof_1_right", -2.0),
        ("vent_3", "roof_1_right", 0.0),
        ("vent_4", "roof_2_left", -4.0),
        ("vent_5", "roof_2_left", -2.0),
        ("vent_6", "roof_2_left", 0.0),
    ]
    assert "no_vents" not in _codes(placed)


def test_a_vent_off_its_roof_or_on_no_surface_is_refused() -> None:
    with pytest.raises(ValidationError, match="vent_3 does not fit on roof_1_right"):
        place_openings(_house(), VENT, ["roof_1_right"], count=3, step=Point2(x=5.0, y=0.0))
    with pytest.raises(ValueError, match="no surface roof_9_right"):
        place_openings(_house(), VENT, ["roof_9_right"])


def test_vents_are_spread_along_each_slope_chosen() -> None:
    spread = spread_openings(_house(), VENT, ["roof_1_right", "roof_1_left"], count=4)

    centres = [(o.surface_id, o.centre.x, o.centre.y) for o in spread.envelope.openings]
    # Each centred on its quarter of the slope's 12 m, at the height asked.
    assert centres == [
        ("roof_1_right", -4.5, 0.0),
        ("roof_1_right", -1.5, 0.0),
        ("roof_1_right", 1.5, 0.0),
        ("roof_1_right", 4.5, 0.0),
        ("roof_1_left", -4.5, 0.0),
        ("roof_1_left", -1.5, 0.0),
        ("roof_1_left", 1.5, 0.0),
        ("roof_1_left", 4.5, 0.0),
    ]
    assert "openings_overlap" not in _codes(spread)


def test_doors_and_vents_are_copied_and_spaced_on_their_surface() -> None:
    house = place_openings(_house(), VENT, ["roof_1_right"])
    copied = repeat_openings(house, ["vent_1"], count=3, step=Point2(x=1.5, y=0.0))
    copied = set_field(copied, ["vent_4"], "centre.x", 4.0)

    spaced = space_openings(copied, ["vent_1", "vent_2", "vent_3", "vent_4"])

    assert [o.centre.x for o in spaced.envelope.openings] == [
        -4.0,
        pytest.approx(-4 / 3),
        pytest.approx(4 / 3),
        4.0,
    ]
    other = place_openings(spaced, VENT, ["roof_2_right"])
    with pytest.raises(ValueError, match="of one surface"):
        space_openings(other, ["vent_1", "vent_2", "vent_5"])


def test_one_field_is_changed_over_the_items_chosen() -> None:
    house = place_items(_house(), HEATER, count=2, step=Vector3(x=2.0, y=0.0, z=0.0))

    changed = set_field(house, ["heater_1", "heater_2"], "power_w", 20_000)
    raised = set_field(changed, ["heater_2"], "base.z", 0.5)

    assert [(p.power_w, p.base.z) for p in _heaters(raised)] == [
        (20_000, 0.0),
        (20_000, 0.5),
    ]


def test_a_field_an_item_has_not_or_a_value_it_cannot_take_is_refused() -> None:
    house = place_items(place_items(_house(), HEATER), FAN)

    with pytest.raises(ValueError, match="fan_1 has no power_w"):
        set_field(house, ["heater_1", "fan_1"], "power_w", 1_000)
    with pytest.raises(ValidationError, match="power_w"):
        set_field(house, ["heater_1"], "power_w", -1)
    with pytest.raises(ValueError, match="rename one item at a time"):
        set_field(house, ["heater_1", "fan_1"], "actuator_id", "unit")
    renamed = set_field(house, ["heater_1"], "actuator_id", "boiler")
    assert _ids(renamed) == ["boiler", "fan_1"]
    with pytest.raises(ValidationError, match="share an identifier"):
        set_field(renamed, ["boiler"], "actuator_id", "fan_1")


def test_chosen_items_are_removed() -> None:
    house = place_openings(
        place_items(_house(), HEATER, count=2, step=Vector3(x=2, y=0, z=0)), VENT, ["roof_1_right"]
    )

    removed = remove_items(house, ["heater_1", "vent_1"])

    assert _ids(removed) == ["heater_2"]
    with pytest.raises(ValueError, match="no item vent_9"):
        remove_items(house, ["vent_9"])


def test_equipment_through_equipment_or_a_rows_support_is_an_error_naming_both() -> None:
    house = place_items(_house(), HEATER)
    # Half through the first heater, and on the first row's first support.
    through = place_items(house, HEATER.model_copy(update={"base": Vector3(x=1.3, y=0.6, z=0)}))
    on_a_row = place_items(house, HEATER.model_copy(update={"base": Vector3(x=4.1, y=2.2, z=0)}))

    (clash,) = [f for f in assess_installation(through) if f.code == "items_collide"]
    assert (clash.severity, clash.items) == ("error", ["heater_1", "heater_2"])
    (on_row,) = [f for f in assess_installation(on_a_row) if f.code == "items_collide"]
    assert on_row.items[0] == "heater_2" and on_row.items[1].startswith("row_1_")


def test_turned_units_whose_boxes_do_not_meet_do_not_collide() -> None:
    # Two square units turned by an eighth of a turn, one along the other's
    # diagonal: the boxes around them, along the house's axes, overlap; the
    # units meet only nearer than their side, 0.6 m, centre to centre.
    turned = HEATER.model_copy(update={"heading": math.pi / 4})
    apart = place_items(_house(), turned, count=2, step=Vector3(x=0.45, y=0.45, z=0.0))
    close = place_items(_house(), turned, count=2, step=Vector3(x=0.4, y=0.4, z=0.0))

    assert "items_collide" not in _codes(apart)
    assert "items_collide" in _codes(close)


def test_doors_or_vents_that_overlap_on_a_surface_are_an_error() -> None:
    house = place_openings(_house(), VENT, ["roof_1_right"], count=2, step=Point2(x=0.5, y=0.0))
    touching = place_openings(_house(), VENT, ["roof_1_right"], count=2, step=Point2(x=1, y=0))

    (overlap,) = [f for f in assess_installation(house) if f.code == "openings_overlap"]
    assert (overlap.severity, overlap.items) == ("error", ["vent_1", "vent_2"])
    assert "openings_overlap" not in _codes(touching)
