"""The reference scenarios (P05.0) are what their design says they are.

`tomato_compartment` is a production compartment of high-wire tomato, the
reference for a full house: rows on gutters, pipe rails, paths, heating
pipes, a service area, a second layout on benches, and open roof vents.
`climate_box` is a small house, shut and still, where climate equipment is
tried; it has one opening of each kind.
"""

from collections import Counter

import pytest

from greenhouse_sim.cfd.geometry import BoundaryCategory
from greenhouse_sim.cfd.openfoam import SetupRefused, flow_roles
from greenhouse_sim.cfd.results import kept_result
from greenhouse_sim.cfd.solve import SOURCE
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.domain.layout import FixtureKind, Obstruction, ZoneKind
from greenhouse_sim.fields.field import EnvironmentField
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services import cfd, fields
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario
from greenhouse_sim.world.geometry import Vector3

COMPARTMENT = scenario("tomato_compartment")
BOX = scenario("climate_box")


def _kinds(config: ScenarioConfig) -> Counter[FixtureKind]:
    """How many whole fixtures of each kind: a support, not its legs; a rail,
    not each of its two tubes."""
    whole = (
        f
        for f in config.layout.fixtures()
        if "_leg_" not in f.fixture_id
        and not (f.kind == FixtureKind.RAIL and f.fixture_id.endswith("_right"))
    )
    return Counter(fixture.kind for fixture in whole)


def test_the_compartment_is_a_venlo_style_house_of_four_spans_and_six_bays() -> None:
    envelope = COMPARTMENT.envelope

    assert (envelope.length, envelope.width) == (24.0, 16.0)
    assert (envelope.eave_height, envelope.ridge_height) == (6.0, 6.8)
    assert (envelope.spans, envelope.bays) == (4, 6)
    assert fields.grid("tomato_compartment").shape == (48, 32, 12)


def test_the_compartments_roof_vents_stand_open_and_its_door_shut() -> None:
    vents = [o for o in COMPARTMENT.envelope.openings if o.kind == OpeningKind.ROOF_VENT]
    (door,) = [o for o in COMPARTMENT.envelope.openings if o.kind == OpeningKind.DOOR]

    assert [v.surface_id for v in vents] == [f"roof_{span}_right" for span in range(1, 5)]
    assert all(v.opening == pytest.approx(0.2) and v.aperture_area() > 0 for v in vents)
    assert door.aperture_area() == 0.0
    assert (door.width, door.height) == (3.0, 3.0)
    # Each vent is an opening of the air's domain, in its ceiling.
    openings = cfd.geometry("tomato_compartment").of(BoundaryCategory.OPENING)
    assert [b.name for b in openings] == [v.opening_id for v in vents]


def test_the_compartment_grows_eight_rows_of_forty_on_gutters_between_pipe_rails() -> None:
    positions = COMPARTMENT.layout.planting_positions()
    kinds = _kinds(COMPARTMENT)

    assert COMPARTMENT.rows * COMPARTMENT.columns == len(positions) == 320
    assert len({p.position_id.split("_position_")[0] for p in positions}) == 8
    assert kinds[FixtureKind.CROP_GUTTER] == 8
    # A rail in each of the seven paths between the rows.
    assert kinds[FixtureKind.RAIL] == 7
    assert kinds[FixtureKind.WIRE] == 8
    assert kinds[FixtureKind.WALKWAY] == 3
    # Four heating pipes along each side wall.
    assert kinds[FixtureKind.PIPE] == 2 * 4


def test_the_compartments_irrigation_unit_stands_in_a_kept_service_area() -> None:
    in_the_air = [f.fixture_id for f in COMPARTMENT.layout.obstructing(Obstruction.AIRFLOW)]
    zones = {zone.zone_id: zone.kind for zone in COMPARTMENT.layout.zones}

    assert "irrigation_unit" in in_the_air
    assert zones == {
        "service_area_back": ZoneKind.SERVICE,
        "keep_out_irrigation": ZoneKind.KEEP_OUT,
    }
    (obstacle,) = cfd.geometry("tomato_compartment").of(BoundaryCategory.OBSTACLE)
    assert obstacle.name == "obstacle_irrigation_unit"


def test_the_compartments_kept_cfd_solution_is_current_and_blows_in_and_out_at_its_vents() -> None:
    grid = fields.grid("tomato_compartment")
    result = kept_result("tomato_compartment", COMPARTMENT, grid)
    assert result is not None, (
        "tomato_compartment's kept CFD result is missing or stale: take it from the CFD "
        "workflow's cfd-results artifact"
    )
    field = EnvironmentField.from_document(result.field)
    vents = {b.name: b for b in cfd.geometry("tomato_compartment").of(BoundaryCategory.OPENING)}

    def below(name: str) -> Vector3:
        box = vents[name].box
        return Vector3(
            x=(box.minimum.x + box.maximum.x) / 2,
            y=(box.minimum.y + box.maximum.y) / 2,
            z=box.minimum.z - grid.cell_size.z / 2,
        )

    assert result.converged and field.grid == grid and field.source == SOURCE
    assert fields.field("tomato_compartment", "cfd").source == SOURCE
    # In through the first vent, at about the setup's speed, and out through
    # the others.
    falling = field.sample(AirQuantity.VELOCITY, below("roof_vent_1"))
    assert isinstance(falling, Vector3) and -0.6 < falling.z < -0.3
    for outlet in ("roof_vent_2", "roof_vent_3", "roof_vent_4"):
        rising = field.sample(AirQuantity.VELOCITY, below(outlet))
        assert isinstance(rising, Vector3) and rising.z > 0


def test_the_compartments_propagation_layout_raises_the_same_rows_on_benches() -> None:
    propagation = changed(COMPARTMENT, SceneChanges(layout="propagation"))

    assert len(propagation.layout.planting_positions()) == 320
    assert _kinds(propagation)[FixtureKind.BENCH] == 8
    assert _kinds(propagation)[FixtureKind.CROP_GUTTER] == 0


def test_the_climate_box_is_a_small_single_span_house_shut_and_still() -> None:
    envelope = BOX.envelope

    assert (envelope.length, envelope.width, envelope.spans, envelope.bays) == (12.0, 6.4, 1, 3)
    assert (envelope.eave_height, envelope.ridge_height) == (4.0, 4.8)
    assert fields.grid("climate_box").shape == (24, 13, 8)
    assert BOX.rows * BOX.columns == len(BOX.layout.planting_positions()) == 32
    assert BOX.airflow.kind == "uniform"
    assert (BOX.airflow.velocity_m_s.x, BOX.airflow.velocity_m_s.y) == (0.0, 0.0)


def test_the_climate_box_has_an_opening_of_each_kind_all_shut() -> None:
    kinds = sorted(opening.kind for opening in BOX.envelope.openings)
    geometry = cfd.geometry("climate_box")

    # A side vent in each side wall, so that a wind across the house has a
    # vent on either side (P07.6).
    assert set(kinds) == set(OpeningKind)
    assert kinds.count(OpeningKind.SIDE_VENT) == 2
    assert all(opening.aperture_area() == 0.0 for opening in BOX.envelope.openings)
    # Shut, its air has no way in or out, so it has no CFD solution.
    assert geometry.of(BoundaryCategory.OPENING) == []
    with pytest.raises(SetupRefused, match="needs two open doors or vents"):
        flow_roles(geometry, BOX.cfd)
