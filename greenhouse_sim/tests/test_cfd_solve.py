"""Solving a scenario's air with OpenFOAM, reading the solution back as a
field, and keeping it by what was solved.

What OpenFOAM writes is read here from cases written in its format, so the
reading is checked without it. With `pytest -m cfd`, gh_001 is solved, and
its solution compared with the one kept in `greenhouse_sim/cfd/results/`.

A kept result goes stale when anything OpenFOAM is given changes. Solve it
again, where OpenFOAM or Docker runs, from `greenhouse_sim/`:

    python -m greenhouse_sim.cfd gh_001 cases/gh_001 --solve

or take `gh_001.json` from the `cfd-results` artifact of the CFD workflow.
"""

import itertools
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from greenhouse_sim.cfd.geometry import BoundaryCategory, cfd_geometry
from greenhouse_sim.cfd.openfoam import (
    INITIAL_FIELDS,
    SOLVE_SCRIPT,
    SetupRefused,
    allrun_script,
    flow_roles,
    solve_case_files,
)
from greenhouse_sim.cfd.results import (
    CfdAirflow,
    CfdResult,
    case_key,
    keep,
    kept_result,
    scenario_key,
)
from greenhouse_sim.cfd.setup import AIR_DENSITY_KG_M3, CfdSetup
from greenhouse_sim.cfd.solve import (
    SOURCE,
    SolveFailed,
    internal_field,
    iterations_taken,
    read_field,
    solve,
)
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldGrid
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services import cfd, fields
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario
from greenhouse_sim.world.geometry import Vector3

GH_001 = scenario("gh_001")
GRID_001 = fields.grid("gh_001")
STALE = (
    "gh_001's kept CFD result is missing or stale: solve it again with "
    "`python -m greenhouse_sim.cfd gh_001 cases/gh_001 --solve`, or take gh_001.json "
    "from the CFD workflow's cfd-results artifact"
)
# A box 2 by 1.5 by 1 m in half-metre cells, 4 by 3 by 2, as a solver meshed
# it with one cell removed.
SMALL = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=2, y=1.5, z=1), 0.5)
REMOVED = (1, 1, 0)


def _with(**setup: object) -> CfdSetup:
    return CfdSetup.model_validate(setup)


def _foam_file(name: str, rows: Sequence[Sequence[float]]) -> str:
    """A field file as OpenFOAM writes it: a list, one entry a line, and a
    patch's own values after it, a short list on one line."""
    vector = len(rows[0]) == 3
    kind, entry = ("volVectorField", "vector") if vector else ("volScalarField", "scalar")
    lines = [f"({' '.join(map(str, r))})" if vector else str(r[0]) for r in rows]
    listed = "\n".join(lines)
    return (
        f"FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class {kind};\n"
        f"    object {name};\n}}\n\ndimensions [0 1 -1 0 0 0 0];\n\n"
        f"internalField   nonuniform List<{entry}> \n{len(rows)}\n(\n{listed}\n)\n;\n\n"
        "boundaryField\n{\n    floor\n    {\n        type noSlip;\n    }\n"
        "    roof_vent_1\n    {\n        type fixedValue;\n"
        f"        value nonuniform List<{entry}> 2({lines[0]} {lines[1]});\n"
        "    }\n}\n"
    )


def _solved_case(directory: Path) -> dict[tuple[int, int, int], tuple[float, float]]:
    """A solved case of the small box in `directory`, its cells in a
    shuffled order; and each cell's centre's x and kinematic pressure, by
    its (i, j, k)."""
    xs, ys, zs = SMALL.centres()
    cells = [
        (i, j, k)
        for k, j, i in itertools.product(range(zs.size), range(ys.size), range(xs.size))
        if (i, j, k) != REMOVED
    ]
    order = np.random.default_rng(7).permutation(len(cells))
    shuffled = [cells[n] for n in order]
    centres = [(float(xs[i]), float(ys[j]), float(zs[k])) for i, j, k in shuffled]
    velocities = [(x, 2 * y, -z) for x, y, z in centres]
    pressures = [(x + y,) for x, y, _ in centres]
    latest = directory / "137"
    latest.mkdir(parents=True)
    (directory / "0").mkdir()
    (latest / "C").write_text(_foam_file("C", centres))
    (latest / "U").write_text(_foam_file("U", velocities))
    (latest / "p").write_text(_foam_file("p", pressures))
    return {
        cell: (centre[0], p[0])
        for cell, centre, p in zip(shuffled, centres, pressures, strict=True)
    }


def test_air_comes_in_through_the_first_open_opening_or_those_named_and_leaves_by_the_rest() -> (
    None
):
    geometry = cfd.geometry("gh_001")
    opened = cfd.geometry("gh_001", SceneChanges(openings={"door_1": 1.0}))

    assert flow_roles(geometry, CfdSetup()).inlets == ["roof_vent_1"]
    assert flow_roles(geometry, CfdSetup()).outlets == ["roof_vent_2"]
    roles = flow_roles(opened, _with(inlets=["door_1"]))
    assert (roles.inlets, roles.outlets) == (["door_1"], ["roof_vent_1", "roof_vent_2"])


@pytest.mark.parametrize(
    ("scenario_id", "setup", "refusal"),
    [
        ("gh_002", CfdSetup(), "needs two open doors or vents"),
        ("gh_001", _with(inlets=["door_1"]), "not door_1"),
        ("gh_001", _with(inlets=["roof_vent_1", "roof_vent_2"]), "no open door or vent left"),
    ],
)
def test_a_setup_without_a_way_in_and_a_way_out_is_refused(
    scenario_id: str, setup: CfdSetup, refusal: str
) -> None:
    with pytest.raises(SetupRefused, match=refusal):
        flow_roles(cfd.geometry(scenario_id), setup)


def test_the_solve_case_drives_the_air_as_its_setup_says() -> None:
    files = solve_case_files(cfd.geometry("gh_001"), _with(inlet_speed_m_s=0.8, iterations=300))
    velocity = files[f"{INITIAL_FIELDS}/U"]
    pressure = files[f"{INITIAL_FIELDS}/p"]

    assert "roof_vent_1\n    {\n        type            surfaceNormalFixedValue;" in velocity
    assert "refValue        uniform -0.8;" in velocity
    assert "roof_vent_2\n    {\n        type            pressureInletOutletVelocity;" in velocity
    assert '".*"\n    {\n        type            noSlip;' in velocity
    assert "roof_vent_2\n    {\n        type            fixedValue;" in pressure
    assert "nu              0.01;" in files["constant/transportProperties"]
    assert "endTime         300;" in files["system/controlDict"]
    assert files[SOLVE_SCRIPT] == allrun_script()
    assert [line.split()[0] for line in allrun_script().splitlines()[4:]] == [
        "./Allmesh",
        "rm",
        "cp",
        "simpleFoam",
        "postProcess",
    ]


def test_a_result_is_keyed_by_everything_openfoam_is_given_and_nothing_else() -> None:
    def key(config: ScenarioConfig) -> str | None:
        return scenario_key("gh_001", config, GRID_001)

    as_configured = key(GH_001)
    longer_run = GH_001.model_copy(update={"duration_days": 99})
    faster = GH_001.model_copy(update={"cfd": _with(inlet_speed_m_s=0.6)})
    vents = changed(GH_001, SceneChanges(openings={"roof_vent_1": 0.5, "door_1": 1.0}))

    assert as_configured == key(longer_run)
    assert len({as_configured, key(faster), key(vents)}) == 3
    assert scenario_key("gh_002", scenario("gh_002"), fields.grid("gh_002")) is None
    files = solve_case_files(cfd.geometry("gh_001"), CfdSetup())
    assert case_key(files) == as_configured
    assert case_key(files | {"system/fvSchemes": "changed"}) != as_configured


def test_values_are_read_whether_uniform_listed_a_line_each_or_on_one_line() -> None:
    assert internal_field("internalField   uniform (0 0 0.5);", 3, 2).tolist() == [
        [0, 0, 0.5],
        [0, 0, 0.5],
    ]
    assert internal_field("internalField   nonuniform List<scalar> 3(1 2 -3e-2);", 1, 3)[
        :, 0
    ].tolist() == [1, 2, -0.03]
    with pytest.raises(SolveFailed, match="3 values, not one for each of 4"):
        internal_field("internalField nonuniform List<scalar> 3(1 2 3);", 1, 4)


def test_a_solution_is_read_onto_the_grid_by_its_cells_centres(tmp_path: Path) -> None:
    solved = _solved_case(tmp_path)

    field = read_field(tmp_path, SMALL, "box_cfd")

    velocity = field.channels[AirQuantity.VELOCITY]
    pressure = field.channels[AirQuantity.PRESSURE]
    xs, ys, zs = SMALL.centres()
    assert field.source == SOURCE and field.field_id == "box_cfd"
    for (i, j, k), (x, p) in solved.items():
        assert velocity[k, j, i].tolist() == pytest.approx([x, 2 * ys[j], -zs[k]])
        assert pressure[k, j, i] == pytest.approx(p * AIR_DENSITY_KG_M3)
    # Inside the removed cell the air is still, at its neighbours' pressure.
    i, j, k = REMOVED
    neighbours = [(i - 1, j, k), (i + 1, j, k), (i, j - 1, k), (i, j + 1, k), (i, j, k + 1)]
    assert velocity[k, j, i].tolist() == [0, 0, 0]
    assert pressure[k, j, i] == pytest.approx(
        np.mean([solved[n][1] for n in neighbours]) * AIR_DENSITY_KG_M3
    )


def test_a_solution_that_does_not_fit_the_grid_is_refused(tmp_path: Path) -> None:
    _solved_case(tmp_path)
    smaller = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=1.5, y=1.5, z=1), 0.5)
    coarser = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=2, y=1.5, z=1), 1.0)

    with pytest.raises(SolveFailed, match="outside the field's grid"):
        read_field(tmp_path, smaller, "box_cfd")
    with pytest.raises(SolveFailed, match="two solved cells lie in one"):
        read_field(tmp_path, coarser, "box_cfd")
    with pytest.raises(SolveFailed, match="holds no solution"):
        read_field(tmp_path / "0", SMALL, "box_cfd")


def test_a_solves_log_says_how_long_it_took_and_whether_it_converged() -> None:
    converged = "Time = 1\n...\nTime = 212\n\nSIMPLE solution converged in 212 iterations\n"
    stopped = "Time = 1\n...\nTime = 2000\n\nEnd\n"

    assert iterations_taken(converged) == (212, True)
    assert iterations_taken(stopped) == (2000, False)


def test_a_result_is_kept_while_it_is_the_scenarios_solution(tmp_path: Path) -> None:
    field = EnvironmentField(
        "gh_001_cfd",
        SOURCE,
        GRID_001,
        0.0,
        {AirQuantity.VELOCITY: np.zeros((*reversed(GRID_001.shape), 3))},
    )
    key = scenario_key("gh_001", GH_001, GRID_001)
    assert key is not None
    result = CfdResult(
        key=key,
        scenario_id="gh_001",
        setup=GH_001.cfd,
        iterations=10,
        converged=True,
        field=field.document(),
    )

    keep(result, tmp_path)

    assert kept_result("gh_001", GH_001, GRID_001, directory=tmp_path) == result
    faster = GH_001.model_copy(update={"cfd": _with(inlet_speed_m_s=0.6)})
    assert kept_result("gh_001", faster, GRID_001, directory=tmp_path) is None
    assert kept_result("gh_demo", scenario("gh_demo"), GRID_001, directory=tmp_path) is None


@pytest.mark.cfd
def test_openfoam_solves_gh_001_to_a_converged_field_on_its_grid(tmp_path: Path) -> None:
    result = solve(cfd.geometry("gh_001"), GH_001.cfd, tmp_path)
    field = EnvironmentField.from_document(result.field)

    assert result.converged and 0 < result.iterations < GH_001.cfd.iterations
    assert result.key == scenario_key("gh_001", GH_001, GRID_001)
    assert field.grid == GRID_001 and field.source == SOURCE
    assert set(field.channels) == {AirQuantity.VELOCITY, AirQuantity.PRESSURE}
    speeds = np.linalg.norm(field.channels[AirQuantity.VELOCITY], axis=-1)
    assert 0.3 < speeds.max() < 1.0


def _kept_001() -> CfdResult:
    result = kept_result("gh_001", GH_001, GRID_001)
    assert result is not None, STALE
    return result


def test_gh_001s_kept_solution_is_its_current_one_and_converged() -> None:
    result = _kept_001()
    field = EnvironmentField.from_document(result.field)

    assert result.converged and result.setup == GH_001.cfd
    assert field.grid == GRID_001 and field.source == SOURCE
    assert set(field.channels) == {AirQuantity.VELOCITY, AirQuantity.PRESSURE}


def test_gh_001s_air_falls_from_its_inlet_vent_and_rises_to_its_outlet_vent() -> None:
    field = EnvironmentField.from_document(_kept_001().field)
    velocity = field.channels[AirQuantity.VELOCITY]
    geometry = cfd_geometry("gh_001", GH_001, GRID_001)
    (obstacle,) = geometry.of(BoundaryCategory.OBSTACLE)

    def below(name: str) -> Vector3:
        (vent,) = [b for b in geometry.boundaries if b.name == name]
        box = vent.box
        return Vector3(
            x=(box.minimum.x + box.maximum.x) / 2,
            y=(box.minimum.y + box.maximum.y) / 2,
            z=box.minimum.z - GRID_001.cell_size.z / 2,
        )

    falling = field.sample(AirQuantity.VELOCITY, below("roof_vent_1"))
    rising = field.sample(AirQuantity.VELOCITY, below("roof_vent_2"))
    assert isinstance(falling, Vector3) and isinstance(rising, Vector3)
    # Square to the inlet at its setup's speed, give or take the mesh's
    # averaging over its cell; out through the outlet.
    assert -0.6 < falling.z < -0.3
    assert rising.z > 0.1
    speeds = np.linalg.norm(velocity, axis=-1)
    assert speeds.max() < 1.0
    # Inside the irrigation unit the air does not move.
    centre = Vector3(
        x=(obstacle.box.minimum.x + obstacle.box.maximum.x) / 2,
        y=(obstacle.box.minimum.y + obstacle.box.maximum.y) / 2,
        z=(obstacle.box.minimum.z + obstacle.box.maximum.z) / 2,
    )
    assert field.sample(AirQuantity.VELOCITY, centre) == Vector3(x=0, y=0, z=0)


def test_a_kept_solution_is_an_airflow_on_any_grid_at_any_time() -> None:
    airflow = CfdAirflow(_kept_001())
    coarse = FieldGrid.over(GRID_001.origin, GRID_001.maximum, 1.0)

    own = airflow.field("gh_001_cfd", GRID_001, time_s=60.0)
    resampled = airflow.field("coarse", coarse)

    assert own.time_s == 60.0 and own.field_id == "gh_001_cfd"
    assert resampled.grid == coarse and resampled.source == SOURCE
    # Each of its cells holds the solution at its centre.
    xs, ys, zs = coarse.centres()
    i, j, k = 0, 5, 1
    centre = Vector3(x=float(xs[i]), y=float(ys[j]), z=float(zs[k]))
    for quantity, values in resampled.channels.items():
        assert np.isfinite(values).all()
        expected = own.sample(quantity, centre)
        if isinstance(expected, Vector3):
            assert values[k, j, i].tolist() == pytest.approx(
                [expected.x, expected.y, expected.z], abs=1e-9
            )
        else:
            assert values[k, j, i] == pytest.approx(expected, abs=1e-9)


def test_a_scenario_offers_its_kept_solution_among_its_fields() -> None:
    _kept_001()

    assert "cfd" in fields.field_names("gh_001")
    assert fields.field("gh_001", "cfd").source == SOURCE
    assert "cfd" not in fields.field_names("gh_002")
    assert {
        sid
        for sid, config in SCENARIO_REGISTRY.items()
        if kept_result(sid, config, fields.grid(sid)) is not None
    } == {"gh_001", "airflow_box"}


@pytest.mark.cfd
def test_openfoam_solves_gh_001_as_its_kept_solution_says(tmp_path: Path) -> None:
    kept = _kept_001()

    # Solved beside the kept result, not in its place.
    solved = solve(cfd.geometry("gh_001"), GH_001.cfd, tmp_path)

    assert solved.converged
    assert solved.key == kept.key
    fresh = EnvironmentField.from_document(solved.field)
    before = EnvironmentField.from_document(kept.field)
    for quantity, values in fresh.channels.items():
        scale = float(np.abs(before.channels[quantity]).max())
        assert np.allclose(values, before.channels[quantity], atol=0.02 * scale), quantity
