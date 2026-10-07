"""The airflow QA case: air blown through `airflow_box` from door to door,
with a block between the doors (its default layout) and without it (`open`).

The block must turn the air around and over it, and leave a slow wake
behind it, in which the air turns back towards it near the floor. These
checks run on the solutions kept for both layouts
(`greenhouse_sim/cfd/results/`), and with `pytest -m cfd` on OpenFOAM's
fresh ones.

The air's velocity and pressure at a few fixed points, its probes, are kept
in `tests/golden/airflow_box_probes.json`, so a change to the solutions
shows as numbers in review. When the kept solutions are solved again, the
probes are written afresh, from `greenhouse_sim/`:

    python tests/test_cfd_wake.py --update
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from greenhouse_sim.cfd.results import kept_result
from greenhouse_sim.cfd.solve import solve
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services import cfd, fields
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario
from greenhouse_sim.world.geometry import Vector3

SCENARIO = "airflow_box"
OPEN = "open"
# Where the block stands: 1 m along the house from x = 5 m, 2 m across it
# about its middle, y = 3.2 m, and 1.5 m high.
MIDDLE_Y = 3.2
BLOCK_HALF_HEIGHT = 0.75
# Points along the house's middle at the block's half height, and beside it
# and over it.
UPSTREAM = Vector3(x=3.0, y=MIDDLE_Y, z=BLOCK_HALF_HEIGHT)
IN_FRONT_HIGH = Vector3(x=4.5, y=MIDDLE_Y, z=1.25)
BESIDE = Vector3(x=5.5, y=1.0, z=BLOCK_HALF_HEIGHT)
OVER = Vector3(x=5.5, y=MIDDLE_Y, z=2.25)
WAKE = Vector3(x=7.0, y=MIDDLE_Y, z=BLOCK_HALF_HEIGHT)
FAR_WAKE = Vector3(x=10.0, y=MIDDLE_Y, z=BLOCK_HALF_HEIGHT)
PROBES = {
    "upstream": UPSTREAM,
    "in_front_high": IN_FRONT_HIGH,
    "beside": BESIDE,
    "over": OVER,
    "wake": WAKE,
    "far_wake": FAR_WAKE,
}
LAYOUTS = (DEFAULT_LAYOUT, OPEN)
PROBES_FILE = Path(__file__).resolve().parent / "golden" / "airflow_box_probes.json"
# Probes are kept to a tenth of a millimetre a second, and of a millipascal.
PROBE_DECIMALS = 4
# A fresh solve's probes agree with the kept ones to within these.
FRESH_VELOCITY_M_S = 0.01
FRESH_PRESSURE_PA = 0.005
STALE = (
    "airflow_box's kept CFD results are missing or stale: solve them again with "
    "`python -m greenhouse_sim.cfd airflow_box cases/airflow_box --solve [--layout open]`, "
    "or take them from the CFD workflow's cfd-results artifact, then update the probes"
)

type Probes = dict[str, dict[str, list[float] | float]]


def _velocity(field: EnvironmentField, point: Vector3) -> Vector3:
    value = field.sample(AirQuantity.VELOCITY, point)
    assert isinstance(value, Vector3)
    return value


def _speed(field: EnvironmentField, point: Vector3) -> float:
    v = _velocity(field, point)
    return float(np.linalg.norm([v.x, v.y, v.z]))


def check_the_wake(blocked: EnvironmentField, unblocked: EnvironmentField) -> None:
    """What the block must do to the air, against the same house without it."""
    # Upstream, the air comes along the house in both.
    assert _velocity(blocked, UPSTREAM).x > 0.1 and _velocity(unblocked, UPSTREAM).x > 0.1
    # In front of the block it rises over it; without it, it hardly does.
    assert _velocity(blocked, IN_FRONT_HIGH).z > 0.05
    assert _velocity(blocked, IN_FRONT_HIGH).z > _velocity(unblocked, IN_FRONT_HIGH).z + 0.05
    # It goes faster beside and over the block than through the open house.
    assert _speed(blocked, BESIDE) > _speed(unblocked, BESIDE)
    assert _velocity(blocked, OVER).x > _velocity(unblocked, OVER).x
    # Behind it, a wake: much slower air than without it...
    assert _speed(blocked, WAKE) < 0.3 * _speed(unblocked, WAKE)
    # ...turning back towards the block, low down, close behind it.
    velocity = blocked.channels[AirQuantity.VELOCITY]
    xs, ys, zs = blocked.grid.centres()
    behind = (xs > 6.0) & (xs < 8.0)
    middle = np.abs(ys - MIDDLE_Y) < 1.0
    low = zs < 1.5
    lee = velocity[np.ix_(low, middle, behind)][..., 0]
    assert lee.min() < 0.0


def probes(field: EnvironmentField) -> Probes:
    """The air's velocity and pressure at each probe."""
    found: Probes = {}
    for name, point in PROBES.items():
        v = _velocity(field, point)
        pressure = field.sample(AirQuantity.PRESSURE, point)
        assert isinstance(pressure, float)
        found[name] = {
            "velocity_m_s": [round(c, PROBE_DECIMALS) for c in (v.x, v.y, v.z)],
            "pressure_pa": round(pressure, PROBE_DECIMALS),
        }
    return found


def _kept(layout: str) -> EnvironmentField:
    config = changed(scenario(SCENARIO), SceneChanges(layout=layout))
    result = kept_result(SCENARIO, config, fields.grid(SCENARIO), layout)
    assert result is not None, STALE
    assert result.converged
    return EnvironmentField.from_document(result.field)


def _kept_probes() -> dict[str, Probes]:
    return {layout: probes(_kept(layout)) for layout in LAYOUTS}


def test_the_kept_solutions_turn_the_air_around_the_block_and_leave_a_wake() -> None:
    check_the_wake(_kept(DEFAULT_LAYOUT), _kept(OPEN))


def test_the_probes_hold_the_kept_solutions_values() -> None:
    assert json.loads(PROBES_FILE.read_text()) == _kept_probes()


def test_the_scenario_offers_its_solution_with_the_layout_asked_for() -> None:
    blocked = fields.field(SCENARIO, "cfd")
    unblocked = fields.field(SCENARIO, "cfd", OPEN)

    assert "cfd" in fields.field_names(SCENARIO, OPEN)
    assert blocked != unblocked
    assert EnvironmentField.from_document(unblocked).sample(
        AirQuantity.VELOCITY, Vector3(x=5.5, y=MIDDLE_Y, z=BLOCK_HALF_HEIGHT)
    ) != Vector3(x=0, y=0, z=0)
    assert EnvironmentField.from_document(blocked).sample(
        AirQuantity.VELOCITY, Vector3(x=5.5, y=MIDDLE_Y, z=BLOCK_HALF_HEIGHT)
    ) == Vector3(x=0, y=0, z=0)


@pytest.mark.cfd
def test_openfoam_solves_air_turning_around_the_block_and_a_wake_behind_it(
    tmp_path: Path,
) -> None:
    config = scenario(SCENARIO)
    blocked = solve(cfd.geometry(SCENARIO), config.cfd, tmp_path / "default")
    unblocked = solve(
        cfd.geometry(SCENARIO, SceneChanges(layout=OPEN)),
        changed(config, SceneChanges(layout=OPEN)).cfd,
        tmp_path / OPEN,
        OPEN,
    )

    assert blocked.converged and unblocked.converged
    check_the_wake(
        EnvironmentField.from_document(blocked.field),
        EnvironmentField.from_document(unblocked.field),
    )
    # As the kept solutions say, at every probe.
    kept = json.loads(PROBES_FILE.read_text())
    for layout, result in ((DEFAULT_LAYOUT, blocked), (OPEN, unblocked)):
        fresh = probes(EnvironmentField.from_document(result.field))
        for name, values in fresh.items():
            assert values["velocity_m_s"] == pytest.approx(
                kept[layout][name]["velocity_m_s"], abs=FRESH_VELOCITY_M_S
            ), (layout, name)
            assert values["pressure_pa"] == pytest.approx(
                kept[layout][name]["pressure_pa"], abs=FRESH_PRESSURE_PA
            ), (layout, name)


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_cfd_wake.py --update")
    PROBES_FILE.write_text(json.dumps(_kept_probes(), indent=2) + "\n")
    print("wrote", PROBES_FILE)
