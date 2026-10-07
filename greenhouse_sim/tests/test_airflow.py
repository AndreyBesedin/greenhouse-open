"""Airflow models: every one, prescribed or solved, satisfies the same field
contract, and each prescribed pattern has the shape of flow it says it
has."""

import math

import numpy as np
import pytest

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.airflow.prescribed import (
    PATTERNS,
    BuoyancyAirflow,
    UniformAirflow,
    VortexAirflow,
)
from greenhouse_sim.cfd.results import CfdAirflow, kept_result
from greenhouse_sim.cfd.solve import SOURCE as CFD_SOURCE
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldGrid
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import fields
from greenhouse_sim.world.geometry import Vector3

# A box 8 by 6 by 3 m, in cells of a quarter metre.
GRID = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=8, y=6, z=3), 0.25)


def _solved() -> CfdAirflow:
    """gh_001's kept CFD solution (see `tests/test_cfd_solve.py`)."""
    result = kept_result("gh_001", SCENARIO_REGISTRY["gh_001"], fields.grid("gh_001"))
    assert result is not None, "gh_001's kept CFD result is missing or stale"
    return CfdAirflow(result)


def _model(name: str) -> AirflowModel:
    return _solved() if name == "cfd" else PATTERNS[name]


MODELS = [*PATTERNS, "cfd"]
SOURCES = {name: f"prescribed:{name}" for name in PATTERNS} | {"cfd": CFD_SOURCE}


def _velocity(field: EnvironmentField) -> np.ndarray:
    return field.channels[AirQuantity.VELOCITY]


def _divergence(field: EnvironmentField) -> np.ndarray:
    """The velocity's divergence at the inner cells, by central differences."""
    v = _velocity(field)
    size = field.grid.cell_size
    dudx = (v[1:-1, 1:-1, 2:, 0] - v[1:-1, 1:-1, :-2, 0]) / (2 * size.x)
    dvdy = (v[1:-1, 2:, 1:-1, 1] - v[1:-1, :-2, 1:-1, 1]) / (2 * size.y)
    dwdz = (v[2:, 1:-1, 1:-1, 2] - v[:-2, 1:-1, 1:-1, 2]) / (2 * size.z)
    divergence: np.ndarray = dudx + dvdy + dwdz
    return divergence


@pytest.mark.parametrize("name", MODELS)
def test_every_model_satisfies_the_field_contract(name: str) -> None:
    model = _model(name)
    field = model.field(f"box_{name}", GRID, time_s=12.0)
    again = model.field(f"box_{name}", GRID, time_s=12.0)

    assert isinstance(field, EnvironmentField)
    assert field.grid == GRID and field.time_s == 12.0
    assert field.source == SOURCES[name]
    assert AirQuantity.VELOCITY in field.channels
    # A prescribed pattern also says how warm the air is; a solve, so far,
    # is isothermal.
    assert (AirQuantity.TEMPERATURE in field.channels) == (name in PATTERNS)
    for quantity, values in field.channels.items():
        assert np.isfinite(values).all()
        assert np.array_equal(values, again.channels[quantity])
    # It publishes, and reads back.
    read = EnvironmentField.from_document(field.document())
    assert np.allclose(_velocity(read), _velocity(field), atol=1e-6)


@pytest.mark.parametrize("model", [BuoyancyAirflow(), VortexAirflow()])
def test_rolls_are_divergence_free_and_never_flow_through_the_walls(
    model: BuoyancyAirflow | VortexAirflow,
) -> None:
    field = model.field("rolls", GRID)
    v = _velocity(field)
    peak = np.linalg.norm(v, axis=-1).max()

    # To the accuracy of central differences on a quarter-metre grid.
    assert np.abs(_divergence(field)).max() < 0.02 * peak / GRID.cell_size.y
    # Next to the side walls the air runs along them, not into them; next to
    # the floor and roof, along them too.
    assert np.abs(v[:, 0, :, 1]).max() < 0.15 * peak and np.abs(v[:, -1, :, 1]).max() < 0.15 * peak
    assert np.abs(v[0, :, :, 2]).max() < 0.15 * peak and np.abs(v[-1, :, :, 2]).max() < 0.15 * peak
    assert peak == pytest.approx(model.peak_speed_m_s, rel=0.05)
    assert np.abs(v[..., 0]).max() == 0.0


def test_convection_rises_up_the_middle_and_sinks_along_the_side_walls() -> None:
    model = BuoyancyAirflow()
    field = model.field("convection", GRID)
    middle_height = Vector3(x=4, y=3, z=1.5)
    near_wall = Vector3(x=4, y=0.4, z=1.5)
    rising = field.sample(AirQuantity.VELOCITY, middle_height)
    sinking = field.sample(AirQuantity.VELOCITY, near_wall)
    low = field.sample(AirQuantity.TEMPERATURE, Vector3(x=4, y=0.4, z=0.2))
    high = field.sample(AirQuantity.TEMPERATURE, Vector3(x=4, y=0.4, z=2.8))
    middle = field.sample(AirQuantity.TEMPERATURE, Vector3(x=4, y=3, z=0.2))
    assert isinstance(rising, Vector3) and isinstance(sinking, Vector3)
    assert isinstance(low, float) and isinstance(high, float) and isinstance(middle, float)

    assert rising.z > 0.2 and sinking.z < 0
    assert high > low and middle > low


def test_a_vortex_turns_one_way_about_the_houses_length() -> None:
    field = VortexAirflow().field("vortex", GRID)
    at = {
        "floor": Vector3(x=4, y=3, z=0.2),
        "roof": Vector3(x=4, y=3, z=2.8),
        "right": Vector3(x=4, y=0.2, z=1.5),
        "left": Vector3(x=4, y=5.8, z=1.5),
    }
    flow = {name: field.sample(AirQuantity.VELOCITY, point) for name, point in at.items()}
    assert all(isinstance(value, Vector3) for value in flow.values())
    floor, roof, right, left = (flow[name] for name in ("floor", "roof", "right", "left"))
    assert isinstance(floor, Vector3) and isinstance(roof, Vector3)
    assert isinstance(right, Vector3) and isinstance(left, Vector3)

    # Along the floor towards +y, up the left wall, back along the roof, down
    # the right wall: one roll.
    assert floor.y > 0 and roof.y < 0 and left.z > 0 and right.z < 0


def test_a_uniform_breeze_is_the_same_everywhere() -> None:
    model = UniformAirflow(velocity_m_s=Vector3(x=0.1, y=0.2, z=0.0), temperature_c=17.0)
    field = model.field("breeze", GRID)

    assert np.allclose(_velocity(field), (0.1, 0.2, 0.0))
    assert np.all(field.channels[AirQuantity.TEMPERATURE] == 17.0)
    corner = field.sample(AirQuantity.VELOCITY, Vector3(x=7.9, y=0.1, z=2.9))
    assert isinstance(corner, Vector3)
    assert [corner.x, corner.y, corner.z] == pytest.approx([0.1, 0.2, 0.0])


def test_each_scenario_names_its_own_airflow_which_it_offers_first() -> None:
    kinds = {scenario_id: config.airflow.kind for scenario_id, config in SCENARIO_REGISTRY.items()}

    assert kinds == {
        "gh_001": "vortex",
        "gh_002": "uniform",
        "gh_demo": "buoyancy",
        "airflow_box": "uniform",
    }
    for scenario_id, kind in kinds.items():
        assert fields.field_names(scenario_id)[0] == kind
        assert fields.configured(scenario_id) == kind
        assert math.isclose(
            fields.grid(scenario_id).maximum.z, SCENARIO_REGISTRY[scenario_id].envelope.eave_height
        )
