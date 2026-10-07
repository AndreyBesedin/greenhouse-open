"""Solved CFD results, kept by what was solved, and offered as airflow.

A result is keyed by its case: a hash of every file written for OpenFOAM
(`openfoam.solve_case_files`). Anything that changes what OpenFOAM is given,
such as the greenhouse's shape, its openings, its obstacles, the setup or
the OpenFOAM version, changes the key. So a kept result is used only while
it is still the solution of the scenario as it is configured.

Each scenario's result is kept in `results/<scenario id>.json` next to this
module, and with another of its layouts in `results/<scenario id>@<layout>.json`,
where `python -m greenhouse_sim.cfd <scenario> <dir> --solve [--layout ...]`
puts it. Solving needs OpenFOAM; reading a kept result does not.
"""

import dataclasses
import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import numpy as np
from pydantic import BaseModel, ConfigDict, NonNegativeInt

from greenhouse_sim.cfd.geometry import cfd_geometry
from greenhouse_sim.cfd.openfoam import OPENFOAM_VERSION, SetupRefused, solve_case_files
from greenhouse_sim.cfd.setup import CfdSetup
from greenhouse_sim.domain.air import VECTOR_QUANTITIES
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument, FieldGrid
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.world.geometry import Vector3

RESULTS_DIR: Final = Path(__file__).parent / "results"


class CfdResult(BaseModel):
    """One solve of a scenario's air, as it is kept."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The hash of the case solved (`case_key`).
    key: str
    scenario_id: str
    # The scenario's layout it was solved with.
    layout: str = DEFAULT_LAYOUT
    setup: CfdSetup
    openfoam: str = OPENFOAM_VERSION
    # How many iterations it took, and whether its residuals fell below the
    # case's tolerances before the setup's limit.
    iterations: NonNegativeInt
    converged: bool
    field: FieldDocument


def case_key(files: Mapping[str, str]) -> str:
    """The hash of a case: every file's path and text."""
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(files[name].encode())
        digest.update(b"\0")
    return digest.hexdigest()


def scenario_key(scenario_id: str, config: ScenarioConfig, grid: FieldGrid) -> str | None:
    """The key of the case that solves a scenario's air as it is configured,
    or None if its setup cannot drive it (it has too few open doors and
    vents, say)."""
    geometry = cfd_geometry(scenario_id, config, grid)
    try:
        return case_key(solve_case_files(geometry, config.cfd))
    except SetupRefused:
        return None


def result_path(
    scenario_id: str, layout: str = DEFAULT_LAYOUT, directory: Path = RESULTS_DIR
) -> Path:
    name = scenario_id if layout == DEFAULT_LAYOUT else f"{scenario_id}@{layout}"
    return directory / f"{name}.json"


def kept_result(
    scenario_id: str,
    config: ScenarioConfig,
    grid: FieldGrid,
    layout: str = DEFAULT_LAYOUT,
    directory: Path = RESULTS_DIR,
) -> CfdResult | None:
    """A scenario's kept result with one of its layouts, `config` being the
    scenario with that layout, if it is the solution of the scenario as it
    is configured now."""
    path = result_path(scenario_id, layout, directory)
    if not path.exists():
        return None
    result = CfdResult.model_validate_json(path.read_text())
    key = scenario_key(scenario_id, config, grid)
    return result if result.key == key and result.layout == layout else None


def keep(result: CfdResult, directory: Path = RESULTS_DIR) -> Path:
    """Keep a result as its scenario's with its layout, in place of any
    before it."""
    path = result_path(result.scenario_id, result.layout, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=1) + "\n")
    return path


class CfdAirflow:
    """A solved result as an airflow model: its steady air, at any time, on
    its own grid or sampled onto another."""

    def __init__(self, result: CfdResult) -> None:
        self.result = result
        self._solved = EnvironmentField.from_document(result.field)

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        solved = self._solved
        if grid == solved.grid:
            return dataclasses.replace(solved, field_id=field_id, time_s=time_s)
        xs, ys, zs = grid.centres()
        channels = {}
        for quantity, values in solved.channels.items():
            sampled = np.zeros((zs.size, ys.size, xs.size, *values.shape[3:]))
            for (k, z), (j, y), (i, x) in _cells(xs, ys, zs):
                value = solved.sample(quantity, _clamped(solved.grid, x, y, z))
                if quantity in VECTOR_QUANTITIES:
                    assert isinstance(value, Vector3)
                    sampled[k, j, i] = (value.x, value.y, value.z)
                else:
                    assert isinstance(value, float)
                    sampled[k, j, i] = value
            channels[quantity] = sampled
        return EnvironmentField(field_id, solved.source, grid, time_s, channels)


def _cells(
    xs: np.ndarray, ys: np.ndarray, zs: np.ndarray
) -> list[tuple[tuple[int, float], tuple[int, float], tuple[int, float]]]:
    return [
        ((k, float(z)), (j, float(y)), (i, float(x)))
        for k, z in enumerate(zs)
        for j, y in enumerate(ys)
        for i, x in enumerate(xs)
    ]


def _clamped(grid: FieldGrid, x: float, y: float, z: float) -> Vector3:
    """A point moved into the grid's box, if it lies outside it."""
    top = grid.maximum
    return Vector3(
        x=min(max(x, grid.origin.x), top.x),
        y=min(max(y, grid.origin.y), top.y),
        z=min(max(z, grid.origin.z), top.z),
    )
