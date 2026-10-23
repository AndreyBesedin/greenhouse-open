"""The contract between equipment and the air (P05.1): commands set levels,
explicitly and replayably, and each piece of equipment supplies what it does
to the air at a level as source terms over a field's grid."""

import numpy as np
import pytest
from pydantic import ValidationError

from greenhouse_sim.climate.commands import Command, Schedule
from greenhouse_sim.climate.sources import HEATER_JET_DIAMETERS, SourceTerms, source_terms
from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services import cfd
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.world.equipment import Dehumidifier, Fan, Heater
from greenhouse_sim.world.geometry import Vector3

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
SOLID = cfd.geometry(PACKAGED, "climate_box").solid()


def _piece[T: Fan | Heater | Dehumidifier](kind: type[T]) -> T:
    """The climate box's one piece of equipment of a kind."""
    (piece,) = [piece for piece in CONFIG.layout.equipment if isinstance(piece, kind)]
    return piece


FAN = _piece(Fan)
HEATER = _piece(Heater)
DEHUMIDIFIER = _piece(Dehumidifier)
IDS = ["fan", "heater", "dehumidifier"]


def _at(time_s: float, actuator_id: str, level: float) -> Command:
    return Command(time_s=time_s, actuator_id=actuator_id, level=level)


def test_every_piece_starts_off_and_stays_at_the_level_last_set() -> None:
    schedule = Schedule.of([_at(600, "heater", 1.0), _at(1800, "heater", 0.25)])

    assert schedule.levels_at(IDS, 0) == {"fan": 0.0, "heater": 0.0, "dehumidifier": 0.0}
    assert schedule.levels_at(IDS, 600)["heater"] == 1.0
    assert schedule.levels_at(IDS, 1799)["heater"] == 1.0
    assert schedule.levels_at(IDS, 3600)["heater"] == 0.25


def test_commands_apply_in_time_order_and_the_later_given_wins_at_a_moment() -> None:
    schedule = Schedule.of(
        [_at(900, "fan", 1.0), _at(0, "heater", 1.0), _at(900, "fan", 0.5), _at(300, "fan", 0.2)]
    )

    assert [(c.time_s, c.actuator_id, c.level) for c in schedule.commands] == [
        (0, "heater", 1.0),
        (300, "fan", 0.2),
        (900, "fan", 1.0),
        (900, "fan", 0.5),
    ]
    assert schedule.levels_at(IDS, 900)["fan"] == 0.5
    assert schedule.moments() == [0, 300, 900]


def test_a_run_logs_the_commands_it_applied_in_order() -> None:
    schedule = Schedule.of([_at(0, "heater", 1.0), _at(300, "fan", 0.2), _at(900, "fan", 1.0)])

    assert schedule.applied(300) == [_at(0, "heater", 1.0), _at(300, "fan", 0.2)]
    assert schedule.applied(-1) == []


def test_a_schedule_replays_the_same_from_its_record() -> None:
    schedule = Schedule.of([_at(0, "heater", 1.0), _at(300, "fan", 0.2), _at(900, "fan", 1.0)])
    replayed = Schedule.model_validate_json(schedule.model_dump_json())

    assert replayed == schedule
    for time_s in (0, 299, 300, 900, 10_000):
        assert replayed.levels_at(IDS, time_s) == schedule.levels_at(IDS, time_s)


def test_levels_set_at_the_start_are_commands_at_time_zero() -> None:
    schedule = Schedule.from_start({"heater": 0.5, "fan": 1.0})

    assert schedule.commands == (_at(0, "fan", 1.0), _at(0, "heater", 0.5))


def test_commands_to_equipment_a_layout_lacks_are_named() -> None:
    schedule = Schedule.of([_at(0, "boiler", 1.0), _at(0, "heater", 1.0), _at(1, "mister", 1)])

    assert schedule.unknown(IDS) == ["boiler", "mister"]
    assert "boiler" not in schedule.levels_at(IDS, 10)


@pytest.mark.parametrize(
    "fields",
    [
        {"time_s": 0, "actuator_id": "fan", "level": 1.5},
        {"time_s": 0, "actuator_id": "fan", "level": -0.1},
        {"time_s": -1, "actuator_id": "fan", "level": 1},
        {"time_s": 0, "actuator_id": "fan", "level": 1, "ramp_s": 60},
    ],
    ids=["above full", "below off", "before the start", "unknown field"],
)
def test_a_command_outside_its_range_is_refused(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Command.model_validate(fields)


def test_a_schedule_given_out_of_order_is_refused() -> None:
    with pytest.raises(ValidationError, match="order of their times"):
        Schedule(commands=[_at(300, "fan", 1.0), _at(0, "fan", 0.0)])


def test_the_climate_box_air_holds_its_units_bodies_as_solid_cells() -> None:
    # The heater's body holds two cells' centres, the dehumidifier's twelve.
    assert SOLID.shape == tuple(reversed(GRID.shape))
    assert int(SOLID.sum()) == 14


@pytest.mark.parametrize("piece", [HEATER, DEHUMIDIFIER], ids=["heater", "dehumidifier"])
def test_a_unit_gives_its_rated_effect_times_its_level_to_the_air_around_it(
    piece: Heater | Dehumidifier,
) -> None:
    full = source_terms(piece, 1.0, GRID, SOLID)
    quarter = source_terms(piece, 0.25, GRID, SOLID)
    heat_w = piece.power_w if isinstance(piece, Heater) else piece.heat_w

    assert full.total_heat_w() == pytest.approx(heat_w)
    assert quarter.total_heat_w() == pytest.approx(heat_w / 4)
    np.testing.assert_allclose(quarter.heat_w, full.heat_w / 4)
    # Into air cells, next to its body, none of them inside it.
    region = full.heat_w > 0
    assert region.any()
    assert not (region & SOLID).any()
    assert not full.velocity.any()


def test_a_dehumidifier_takes_its_rated_water_times_its_level_from_the_same_air() -> None:
    terms = source_terms(DEHUMIDIFIER, 0.5, GRID, SOLID)

    assert terms.total_water_removed_kg_s() == pytest.approx(1.0 / HOUR_S / 2)
    np.testing.assert_array_equal(terms.water_removed_kg_s > 0, terms.heat_w > 0)
    assert source_terms(HEATER, 1.0, GRID, SOLID).total_water_removed_kg_s() == 0.0


def test_the_air_around_a_unit_lies_within_a_cell_of_its_body() -> None:
    terms = source_terms(DEHUMIDIFIER, 1.0, GRID, SOLID)
    xs, ys, zs = GRID.centres()
    cells = np.argwhere(terms.heat_w > 0)
    low, high = DEHUMIDIFIER.fixture().bounds()
    size = GRID.cell_size

    for k, j, i in cells:
        assert low.x - size.x <= xs[i] <= high.x + size.x
        assert low.y - size.y <= ys[j] <= high.y + size.y
        assert low.z <= zs[k] <= high.z + size.z


def test_a_heaters_heat_lies_in_its_jet_ahead_of_its_outlet() -> None:
    """A unit heater blows its warm air out of its front (#261): its heat is
    given to the cells ahead of it along its heading, up to its jet's
    length, most to those nearest its outlet's axis, all of it."""
    terms = source_terms(HEATER, 1.0, GRID, SOLID)
    xs, ys, zs = GRID.centres()
    axis = HEATER.facing()
    outlet = HEATER.base.x + axis.x * HEATER.size_x / 2, HEATER.base.y + axis.y * HEATER.size_x / 2
    length = HEATER_JET_DIAMETERS * min(HEATER.size_y, HEATER.size_z)
    cells = np.argwhere(terms.heat_w > 0)

    assert terms.total_heat_w() == pytest.approx(HEATER.power_w)
    assert len(cells) > len(np.argwhere(source_terms(DEHUMIDIFIER, 1.0, GRID, SOLID).heat_w > 0))
    for _, j, i in cells:
        along = (xs[i] - outlet[0]) * axis.x + (ys[j] - outlet[1]) * axis.y
        assert 0.0 <= along <= length
    k, j, i = np.unravel_index(int(np.argmax(terms.heat_w)), terms.heat_w.shape)
    assert abs(zs[k] - HEATER.size_z / 2) <= GRID.cell_size.z


def _axis_cell(along_m: float) -> tuple[int, int, int]:
    """The cell, in the grid's order (z, y, x), that the heater's outlet's
    axis passes `along_m` in front of its outlet."""
    axis = HEATER.facing()
    x = HEATER.base.x + axis.x * (HEATER.size_x / 2 + along_m)
    y = HEATER.base.y + axis.y * (HEATER.size_x / 2 + along_m)
    z = HEATER.base.z + HEATER.size_z / 2
    size = GRID.cell_size
    return (
        int((z - GRID.origin.z) // size.z),
        int((y - GRID.origin.y) // size.y),
        int((x - GRID.origin.x) // size.x),
    )


def test_a_heaters_jet_is_warmest_on_its_axis() -> None:
    """Shared as a round jet's speed is: across it, most on its axis."""
    k, j, i = _axis_cell(2.0)
    heat = source_terms(HEATER, 1.0, GRID, SOLID).heat_w

    assert heat[k, j, i] > heat[k, j + 1, i] > heat[k, j + 2, i] >= 0.0


def test_a_heater_whose_outlet_is_blocked_warms_the_air_around_its_body() -> None:
    blocked = SOLID.copy()
    blocked[_axis_cell(0.1)] = True
    terms = source_terms(HEATER, 1.0, GRID, blocked)
    xs, ys, zs = GRID.centres()
    low, high = HEATER.fixture().bounds()
    size = GRID.cell_size

    assert terms.total_heat_w() == pytest.approx(HEATER.power_w)
    for k, j, i in np.argwhere(terms.heat_w > 0):
        assert low.x - size.x <= xs[i] <= high.x + size.x
        assert low.y - size.y <= ys[j] <= high.y + size.y
        assert low.z <= zs[k] <= high.z + size.z


def test_a_heaters_jet_stops_at_an_obstacle_on_its_axis() -> None:
    obstructed = SOLID.copy()
    obstacle = _axis_cell(2.0)
    obstructed[obstacle] = True
    terms = source_terms(HEATER, 1.0, GRID, obstructed)
    xs, _, _ = GRID.centres()

    assert terms.total_heat_w() == pytest.approx(HEATER.power_w)
    # Its heading is along -x: nothing beyond the obstacle is warmed.
    assert not terms.heat_w[:, :, : obstacle[2]].any()
    assert terms.heat_w[:, :, obstacle[2] + 1 :].any()
    assert xs[obstacle[2]] < HEATER.base.x


def test_a_jet_too_narrow_for_any_cell_warms_the_cells_its_axis_passes() -> None:
    """A heater whose outlet is a few centimetres wide: no cell's centre lies
    in its jet, so its heat goes along its axis, not back around its body."""
    narrow = HEATER.model_copy(update={"size_y": 0.1, "size_z": 0.1})
    terms = source_terms(narrow, 1.0, GRID, SOLID)
    xs, _, _ = GRID.centres()
    outlet_x = narrow.base.x + narrow.facing().x * narrow.size_x / 2

    assert terms.total_heat_w() == pytest.approx(narrow.power_w)
    heated = np.argwhere(terms.heat_w > 0)
    assert {(k, j) for k, j, _ in heated} == {(0, 1)}
    assert all(xs[i] <= outlet_x for _, _, i in heated)


@pytest.mark.parametrize("piece", [FAN, HEATER, DEHUMIDIFIER], ids=IDS)
def test_equipment_that_is_off_does_nothing(piece: Fan | Heater | Dehumidifier) -> None:
    terms = source_terms(piece, 0.0, GRID, SOLID)

    assert not terms.velocity.any()
    assert not terms.heat_w.any()
    assert not terms.water_removed_kg_s.any()


def test_a_unit_hemmed_in_gives_its_effect_to_the_nearest_air_cell() -> None:
    solid = np.ones_like(SOLID)
    solid[0, 1, 22] = False
    terms = source_terms(HEATER, 1.0, GRID, solid)

    assert terms.total_heat_w() == pytest.approx(HEATER.power_w)
    assert terms.heat_w[0, 1, 22] == pytest.approx(HEATER.power_w)


def test_source_terms_add_up_on_one_grid_and_refuse_another() -> None:
    heater = source_terms(HEATER, 1.0, GRID, SOLID)
    dehumidifier = source_terms(DEHUMIDIFIER, 1.0, GRID, SOLID)
    both = heater + dehumidifier
    other = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=1, y=1, z=1), 0.5)

    assert both.total_heat_w() == pytest.approx(HEATER.power_w + DEHUMIDIFIER.heat_w)
    assert (SourceTerms.none(GRID) + heater).total_heat_w() == heater.total_heat_w()
    with pytest.raises(ValueError, match="different grids"):
        heater + SourceTerms.none(other)
