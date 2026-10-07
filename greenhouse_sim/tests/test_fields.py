"""The environment field format: a regular grid over a box, channels of the
air's quantities at its cells' centres, interpolation between them, and the
document a viewer reads.

`greenhouse_sim/fields/field.schema.json` is the schema the viewer generates
its field types from and validates fields against. It is written here, from
`greenhouse_sim/`:

    python tests/test_fields.py --update
"""

import base64
import json
import math
import sys
from http import HTTPStatus
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import (
    CellCounts,
    EnvironmentField,
    FieldDocument,
    FieldGrid,
    field_json_schema,
)
from greenhouse_sim.fields.synthetic import shear_field, shear_temperature, shear_velocity
from greenhouse_sim.services import fields
from greenhouse_sim.world.geometry import Vector3

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "greenhouse_sim" / "fields" / "field.schema.json"
# A box 4 by 3 by 2 m, in cells of 0.5 m.
GRID = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=4, y=3, z=2), 0.5)
SHEAR = shear_field("box_shear", GRID)


def _close(found: Vector3 | float | None, expected: Vector3 | float) -> bool:
    if isinstance(expected, Vector3):
        assert isinstance(found, Vector3)
        return math.dist((found.x, found.y, found.z), (expected.x, expected.y, expected.z)) < 1e-9
    assert isinstance(found, float)
    return abs(found - expected) < 1e-9


def test_a_grid_divides_its_box_into_cells_no_wider_than_asked() -> None:
    uneven = FieldGrid.over(Vector3(x=1, y=0, z=0), Vector3(x=4.5, y=2.2, z=1), 0.5)

    assert GRID.shape == (8, 6, 4)
    assert uneven.shape == (7, 5, 2)
    assert uneven.cell_size.y == pytest.approx(0.44)
    top = uneven.maximum
    assert (top.x, top.z) == (4.5, 1.0)
    assert top.y == pytest.approx(2.2)
    xs, _, zs = uneven.centres()
    assert xs[0] == pytest.approx(1.25) and zs.tolist() == [0.25, 0.75]


@pytest.mark.parametrize(
    "point",
    [
        Vector3(x=0.25, y=0.25, z=0.25),
        Vector3(x=1.0, y=1.5, z=1.0),
        Vector3(x=2.3, y=0.7, z=1.61),
        Vector3(x=3.75, y=2.75, z=1.75),
    ],
)
def test_an_analytic_field_sampled_at_known_points_has_its_known_values(point: Vector3) -> None:
    assert _close(SHEAR.sample(AirQuantity.VELOCITY, point), shear_velocity(point))
    assert _close(SHEAR.sample(AirQuantity.TEMPERATURE, point), shear_temperature(point))


def test_beyond_the_outermost_centres_a_field_holds_their_values_and_outside_says_nothing() -> None:
    near_floor = Vector3(x=1.0, y=1.0, z=0.1)
    lowest_centre = Vector3(x=1.0, y=1.0, z=0.25)

    assert SHEAR.sample(AirQuantity.TEMPERATURE, near_floor) == SHEAR.sample(
        AirQuantity.TEMPERATURE, lowest_centre
    )
    assert SHEAR.sample(AirQuantity.VELOCITY, Vector3(x=4.01, y=1, z=1)) is None
    assert SHEAR.sample(AirQuantity.VELOCITY, Vector3(x=1, y=1, z=-0.01)) is None
    assert SHEAR.sample(AirQuantity.CO2, Vector3(x=1, y=1, z=1)) is None


def test_a_field_of_one_cell_holds_one_value_everywhere() -> None:
    single = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=1, y=1, z=1), 2.0)
    field = EnvironmentField(
        field_id="one",
        source="test",
        grid=single,
        time_s=0.0,
        channels={AirQuantity.CO2: np.full((1, 1, 1), 800.0)},
    )

    assert single.shape == (1, 1, 1)
    assert field.sample(AirQuantity.CO2, Vector3(x=0.9, y=0.1, z=0.5)) == 800.0


def test_a_channel_of_the_wrong_shape_or_with_values_that_are_not_finite_is_refused() -> None:
    nx, ny, nz = GRID.shape
    with pytest.raises(ValueError, match="velocity has shape"):
        EnvironmentField("bad", "test", GRID, 0.0, {AirQuantity.VELOCITY: np.zeros((nz, ny, nx))})
    broken = np.zeros((nz, ny, nx))
    broken[1, 2, 3] = np.nan
    with pytest.raises(ValueError, match="not finite"):
        EnvironmentField("bad", "test", GRID, 0.0, {AirQuantity.TEMPERATURE: broken})
    with pytest.raises(ValidationError, match="positive"):
        FieldGrid(
            origin=Vector3(x=0, y=0, z=0),
            cell_size=Vector3(x=1, y=0, z=1),
            cells=CellCounts(x=1, y=1, z=1),
        )


def test_values_run_x_fastest_then_y_then_z_with_a_vectors_components_fastest() -> None:
    document = SHEAR.document()
    velocity = next(c for c in document.channels if c.quantity == AirQuantity.VELOCITY)
    temperature = next(c for c in document.channels if c.quantity == AirQuantity.TEMPERATURE)
    values = np.frombuffer(base64.b64decode(temperature.data), dtype="<f4")
    nx, ny, _ = GRID.shape
    i, j, k = 3, 2, 1
    centre = Vector3(x=(i + 0.5) * 0.5, y=(j + 0.5) * 0.5, z=(k + 0.5) * 0.5)

    assert values[(k * ny + j) * nx + i] == pytest.approx(shear_temperature(centre), abs=1e-5)
    assert (velocity.components, temperature.components) == (3, 1)
    assert (velocity.unit, temperature.unit) == ("m/s", "°C")
    assert velocity.minimum == pytest.approx(0.25 * 0.25)
    assert velocity.maximum == pytest.approx(0.25 * 1.75)


def test_a_field_published_and_read_back_is_the_same_to_single_precision() -> None:
    document = FieldDocument.model_validate_json(SHEAR.document().model_dump_json())
    read = EnvironmentField.from_document(document)

    assert read.grid == SHEAR.grid and read.source == "synthetic:shear"
    for quantity, values in SHEAR.channels.items():
        assert np.allclose(read.channels[quantity], values, atol=1e-5)


def test_the_published_schema_matches_the_field_document() -> None:
    assert json.loads(SCHEMA_FILE.read_text()) == json.loads(json.dumps(field_json_schema()))


def test_a_scenario_offers_its_fields_over_its_greenhouses_air() -> None:
    answer = respond("GET", "/api/scenarios/tomato_compartment/fields/shear")
    missing = respond("GET", "/api/scenarios/tomato_compartment/fields/wind")
    nowhere = respond("GET", "/api/scenarios/gh_999/fields/shear")
    document = FieldDocument.model_validate(answer.body)

    assert answer.status == HTTPStatus.OK
    assert document.grid == fields.grid("tomato_compartment")
    # Up to the compartment's gutters, 6 m above its floor.
    assert document.grid.maximum.z == pytest.approx(6.0)
    assert max(document.grid.cell_size.x, document.grid.cell_size.y) <= fields.CELL_M
    assert (missing.status, missing.body) == (
        HTTPStatus.NOT_FOUND,
        {
            "error": "scenario 'tomato_compartment' has no field 'wind'; "
            "it has buoyancy, uniform, vortex, cfd, shear"
        },
    )
    assert nowhere.status == HTTPStatus.NOT_FOUND
    listed = respond("GET", "/api/scenarios/tomato_compartment/fields")
    assert (listed.status, listed.body) == (
        HTTPStatus.OK,
        {"fields": ["buoyancy", "uniform", "vortex", "cfd", "shear"], "configured": "buoyancy"},
    )
    assert respond("GET", "/api/scenarios/gh_999/fields").status == HTTPStatus.NOT_FOUND


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_fields.py --update")
    SCHEMA_FILE.write_text(json.dumps(field_json_schema(), indent=2, ensure_ascii=False) + "\n")
    print("wrote", SCHEMA_FILE)
