"""Solving a scenario's air with OpenFOAM, and reading its solution back as
an environment field.

`solve` writes the case (`openfoam.solve_case_files`), runs its `Allrun`
script wherever OpenFOAM runs (`runner`), and reads the solution at its last
iteration: each cell's velocity and kinematic pressure, and its centre.
Since the mesh's cells are the field grid's cells, less those obstacles
removed, each value goes to the grid cell its centre lies in, and nothing is
interpolated.

Inside an obstacle the air does not move, and its pressure is taken as its
neighbours' mean, so the field says something everywhere in its box.
"""

import re
from pathlib import Path
from typing import Final

import numpy as np

from greenhouse_sim.cfd import runner
from greenhouse_sim.cfd.geometry import CfdGeometry
from greenhouse_sim.cfd.openfoam import (
    LOG_TAIL,
    OPENFOAM_VERSION,
    SOLVE_SCRIPT,
    solve_case_files,
    write_case,
)
from greenhouse_sim.cfd.results import CfdResult, case_key
from greenhouse_sim.cfd.setup import AIR_DENSITY_KG_M3, CfdSetup
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, EnvironmentField, FieldGrid
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT

# What made a solved field, as its source says.
SOURCE: Final = f"openfoam:simpleFoam {OPENFOAM_VERSION}"
_CONVERGED = re.compile(r"SIMPLE solution converged in (\d+) iterations")
_ITERATION = re.compile(r"^Time = (\d+)\s*$", re.MULTILINE)
_UNIFORM = re.compile(r"internalField\s+uniform\s+([^;]+);")
_NONUNIFORM = re.compile(r"internalField\s+nonuniform\s+List<\w+>\s*(\d+)\s*\(")


class SolveFailed(RuntimeError):
    """OpenFOAM could not solve the case, or its solution could not be read."""


def internal_field(text: str, components: int, cells: int) -> np.ndarray:
    """A field file's values at the cells, one row per cell, from OpenFOAM's
    plain-text format: a uniform value, or a list of one per cell."""
    uniform = _UNIFORM.search(text)
    if uniform is not None:
        value = np.array(uniform.group(1).strip("() ").split(), dtype=float)
        return np.tile(value, (cells, 1)).reshape(cells, components)
    listed = _NONUNIFORM.search(text)
    if listed is None:
        raise SolveFailed("a field file holds neither a uniform value nor a list")
    count = int(listed.group(1))
    end = _closing(text, listed.end())
    values = np.array(
        text[listed.end() : end].replace("(", " ").replace(")", " ").split(), dtype=float
    )
    if count != cells or values.size != cells * components:
        raise SolveFailed(f"a field file holds {count} values, not one for each of {cells} cells")
    return values.reshape(cells, components)


def _closing(text: str, start: int) -> int:
    """Where the list opened just before `start` closes: OpenFOAM writes a
    long list one entry a line, and a short one on one line."""
    depth = 1
    for bracket in re.compile(r"[()]").finditer(text, start):
        depth += 1 if bracket.group() == "(" else -1
        if depth == 0:
            return bracket.start()
    raise SolveFailed("a field file's list does not close")


def _latest_time(directory: Path) -> Path:
    times = [p for p in directory.iterdir() if p.is_dir() and re.fullmatch(r"\d+", p.name)]
    solved = [p for p in times if p.name != "0"]
    if not solved:
        raise SolveFailed(f"{directory} holds no solution")
    return max(solved, key=lambda p: int(p.name))


def _cell_indices(centres: np.ndarray, grid: FieldGrid) -> tuple[np.ndarray, ...]:
    """The grid cell (k, j, i) each centre lies in: each solver cell is one
    of the grid's."""
    origin = np.array([grid.origin.x, grid.origin.y, grid.origin.z])
    size = np.array([grid.cell_size.x, grid.cell_size.y, grid.cell_size.z])
    # A centre lies halfway across its cell, well clear of its edges.
    indices = np.floor((centres - origin) / size).astype(int)
    if (indices < 0).any() or (indices >= np.array(grid.shape)).any():
        raise SolveFailed("a solved cell lies outside the field's grid")
    if len({tuple(row) for row in indices}) != len(indices):
        raise SolveFailed("two solved cells lie in one of the field's cells")
    i, j, k = indices.T
    return k, j, i


def _filled(values: np.ndarray) -> np.ndarray:
    """A scalar grid with its gaps (NaN) filled, layer by layer from their
    edges, with the mean of the neighbours already known."""
    filled = values.copy()
    while np.isnan(filled).any():
        known = ~np.isnan(filled)
        total = np.zeros_like(filled)
        count = np.zeros_like(filled)
        for axis in range(filled.ndim):
            for shift in (1, -1):
                neighbour = np.roll(np.where(known, filled, 0.0), shift, axis=axis)
                present = np.roll(known, shift, axis=axis).astype(float)
                # np.roll wraps around; a cell has no neighbour past the edge.
                edge = [slice(None)] * filled.ndim
                edge[axis] = slice(0, 1) if shift == 1 else slice(-1, None)
                neighbour[tuple(edge)] = 0.0
                present[tuple(edge)] = 0.0
                total += neighbour
                count += present
        reachable = ~known & (count > 0)
        if not reachable.any():
            raise SolveFailed("the pressure is known in none of the field's cells")
        filled[reachable] = total[reachable] / count[reachable]
    return filled


def read_field(directory: Path, grid: FieldGrid, field_id: str) -> EnvironmentField:
    """A solved case's last solution as a field on `grid`: velocity, and
    pressure in pascals above the outside's."""
    latest = _latest_time(directory)
    centres_text = (latest / "C").read_text()
    # Every cell's centre differs, so they are listed, and say how many cells
    # there are.
    listed = _NONUNIFORM.search(centres_text)
    if listed is None:
        raise SolveFailed(f"{latest / 'C'} does not list the cells' centres")
    cells = int(listed.group(1))
    centres = internal_field(centres_text, VECTOR_COMPONENTS, cells)
    velocity = internal_field((latest / "U").read_text(), VECTOR_COMPONENTS, cells)
    pressure = internal_field((latest / "p").read_text(), 1, cells)[:, 0] * AIR_DENSITY_KG_M3
    k, j, i = _cell_indices(centres, grid)
    nx, ny, nz = grid.shape
    velocities = np.zeros((nz, ny, nx, VECTOR_COMPONENTS))
    velocities[k, j, i] = velocity
    pressures = np.full((nz, ny, nx), np.nan)
    pressures[k, j, i] = pressure
    return EnvironmentField(
        field_id=field_id,
        source=SOURCE,
        grid=grid,
        time_s=0.0,
        channels={AirQuantity.VELOCITY: velocities, AirQuantity.PRESSURE: _filled(pressures)},
    )


def iterations_taken(log: str) -> tuple[int, bool]:
    """How many iterations a solve took, and whether it converged."""
    converged = _CONVERGED.search(log)
    if converged is not None:
        return int(converged.group(1)), True
    steps = _ITERATION.findall(log)
    return (int(steps[-1]) if steps else 0), False


def solve(
    geometry: CfdGeometry, setup: CfdSetup, directory: Path, layout: str = DEFAULT_LAYOUT
) -> CfdResult:
    """Write the case that solves the geometry's air as the setup drives it
    into `directory`, solve it with OpenFOAM, and return its solution. The
    geometry is its scenario's with `layout`."""
    files = solve_case_files(geometry, setup)
    write_case(files, directory)
    run = runner.run(directory, f"./{SOLVE_SCRIPT}")
    if run.returncode != 0:
        logs = sorted(directory.glob("log.*"), key=lambda log: log.stat().st_mtime)
        last = logs[-1].read_text()[-LOG_TAIL:] if logs else run.stderr[-LOG_TAIL:]
        raise SolveFailed(f"{SOLVE_SCRIPT} failed:\n{last}")
    iterations, converged = iterations_taken((directory / "log.simpleFoam").read_text())
    field = read_field(directory, geometry.grid, f"{geometry.scenario_id}_cfd")
    return CfdResult(
        key=case_key(files),
        scenario_id=geometry.scenario_id,
        layout=layout,
        setup=setup,
        iterations=iterations,
        converged=converged,
        field=field.document(),
    )
