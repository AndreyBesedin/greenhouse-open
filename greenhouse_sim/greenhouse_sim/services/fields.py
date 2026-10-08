"""A scenario's environment fields: its greenhouse's air, as a client draws it.

A field covers the air under the greenhouse's gutters: its floor, from its
front right corner, up to its eaves. The air in the roof's spans above them
is left out until a solver needs it. Its cells are at most `CELL_M` wide.

A scenario offers every prescribed airflow pattern
(`greenhouse_sim.airflow.prescribed`): its own, as its configuration sets
it, first, and the others with their typical numbers. Then its CFD solution
(`cfd`) with the layout asked for, if one is kept that is still its
solution (`greenhouse_sim.cfd.results`). Then, if its layout places
equipment, its `climate`: its air through a climate run, with its equipment
running at the levels asked from the start, all off unless asked, and its
doors and vents open as asked, at a moment of the run
(`greenhouse_sim.climate.run`). And last the synthetic
shear the field format is checked against.

A few recent climate runs are kept, each with the moments asked of it, so
that a later moment carries on from the latest before it.
"""

import functools
from collections.abc import Mapping
from typing import Final

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.airflow.prescribed import PATTERNS
from greenhouse_sim.cfd.geometry import cfd_geometry
from greenhouse_sim.cfd.results import CfdAirflow, kept_result
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument, FieldGrid
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.scenarios import SceneChanges, changed, equipment_levels, scenario
from greenhouse_sim.world.geometry import Vector3

# The widest a field's cell may be, in metres.
CELL_M: Final = 0.5
SHEAR: Final = "shear"
CFD: Final = "cfd"
CLIMATE: Final = "climate"
# How long a climate run lasts, at most, in seconds: an hour.
LONGEST_RUN_S: Final = 3600.0
# How many recent climate runs are kept.
KEPT_RUNS: Final = 8


class _Shear:
    """The synthetic shear, as an airflow model."""

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        return shear_field(field_id, grid)


type _Pairs = tuple[tuple[str, float], ...]


@functools.lru_cache(maxsize=KEPT_RUNS)
def _climate_run(scenario_id: str, layout: str, levels: _Pairs, openings: _Pairs) -> ClimateRun:
    """A scenario's climate run with one of its layouts, its equipment set to
    `levels` from the start, and its doors and vents open as `openings` say."""
    config = changed(scenario(scenario_id), SceneChanges(layout=layout, openings=dict(openings)))
    grid = air_grid(config)
    geometry = cfd_geometry(scenario_id, config, grid)
    apertures = {
        opening.opening_id: opening.aperture_area() for opening in config.envelope.openings
    }
    vents = [
        Vent(
            opening_id=opening_id,
            aperture_m2=apertures[opening_id],
            cells=cells,
            axis=axis,
            outward=outward,
        )
        for opening_id, (cells, axis, outward) in geometry.opening_cells().items()
    ]
    return ClimateRun(
        base=config.airflow,
        equipment=config.layout.equipment,
        schedule=Schedule.from_start(dict(levels)),
        settings=config.climate,
        grid=grid,
        solid=geometry.solid(),
        vents=vents,
    )


class _Climate:
    """A scenario's climate, as an airflow model: its run is made, or found
    among the kept ones, only when it is drawn."""

    def __init__(
        self,
        scenario_id: str,
        layout: str,
        levels: Mapping[str, float],
        openings: Mapping[str, float],
    ):
        self._key = (
            scenario_id,
            layout,
            tuple(sorted(levels.items())),
            tuple(sorted(openings.items())),
        )

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        return _climate_run(*self._key).field(field_id, grid, time_s)


def _models(
    scenario_id: str,
    layout: str,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
) -> dict[str, AirflowModel]:
    """A scenario's fields by name, with one of its layouts, its equipment at
    `levels` and its doors and vents open as `openings` say: its own airflow
    first."""
    config = changed(
        scenario(scenario_id), SceneChanges(layout=layout, openings=dict(openings or {}))
    )
    running = equipment_levels(config, levels or {})
    own = config.airflow
    models: dict[str, AirflowModel] = {own.kind: own}
    for name, pattern in PATTERNS.items():
        models.setdefault(name, pattern)
    solved = kept_result(scenario_id, config, air_grid(config), layout)
    if solved is not None:
        models[CFD] = CfdAirflow(solved)
    if config.layout.equipment:
        models[CLIMATE] = _Climate(scenario_id, layout, running, openings or {})
    models[SHEAR] = _Shear()
    return models


def field_names(scenario_id: str, layout: str | None = None) -> list[str]:
    """The fields a scenario offers with one of its layouts, by default its
    own, its own airflow first. Only its CFD solution depends on the
    layout."""
    return list(_models(scenario_id, layout or DEFAULT_LAYOUT))


def configured(scenario_id: str) -> str:
    """The name of a scenario's own airflow."""
    return scenario(scenario_id).airflow.kind


def grid(scenario_id: str) -> FieldGrid:
    """The grid a scenario's fields cover: its greenhouse's air under the
    gutters."""
    return air_grid(scenario(scenario_id))


def air_grid(config: ScenarioConfig) -> FieldGrid:
    """The grid over a scenario's greenhouse's air under the gutters, as it
    is configured."""
    envelope = config.envelope
    return FieldGrid.over(
        Vector3(x=0.0, y=0.0, z=0.0),
        Vector3(x=envelope.length, y=envelope.width, z=envelope.eave_height),
        CELL_M,
    )


def field(
    scenario_id: str,
    name: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    time_s: float = 0.0,
    openings: Mapping[str, float] | None = None,
) -> FieldDocument:
    """One of a scenario's fields with one of its layouts, by default its
    own, its equipment at `levels` and its doors and vents open as `openings`
    say, at `time_s` into a climate run, as it is published. A level for
    equipment it does not have, or outside 0 to 1, is refused, as are an
    opening it does not have and a moment outside a run."""
    if not 0.0 <= time_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a climate run lasts from 0 to {LONGEST_RUN_S:g} s, not {time_s:g}")
    models = _models(scenario_id, layout or DEFAULT_LAYOUT, levels, openings)
    model = models.get(name)
    if model is None:
        known = ", ".join(models)
        raise NotFound(f"scenario {scenario_id!r} has no field {name!r}; it has {known}")
    return model.field(f"{scenario_id}_{name}", grid(scenario_id), time_s).document()
