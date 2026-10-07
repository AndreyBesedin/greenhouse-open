"""A scenario's environment fields: its greenhouse's air, as a client draws it.

A field covers the air under the greenhouse's gutters: its floor, from its
front right corner, up to its eaves. The air in the roof's spans above them
is left out until a solver needs it. Its cells are at most `CELL_M` wide.

A scenario offers every prescribed airflow pattern
(`greenhouse_sim.airflow.prescribed`): its own, as its configuration sets
it, first, and the others with their typical numbers. Then its CFD solution
(`cfd`) with the layout asked for, if one is kept that is still its
solution (`greenhouse_sim.cfd.results`), and the synthetic shear the field
format is checked against.
"""

from typing import Final

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.airflow.prescribed import PATTERNS
from greenhouse_sim.cfd.results import CfdAirflow, kept_result
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument, FieldGrid
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario
from greenhouse_sim.world.geometry import Vector3

# The widest a field's cell may be, in metres.
CELL_M: Final = 0.5
SHEAR: Final = "shear"
CFD: Final = "cfd"


class _Shear:
    """The synthetic shear, as an airflow model."""

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        return shear_field(field_id, grid)


def _models(scenario_id: str, layout: str) -> dict[str, AirflowModel]:
    """A scenario's fields by name, with one of its layouts: its own airflow
    first."""
    config = changed(scenario(scenario_id), SceneChanges(layout=layout))
    own = config.airflow
    models: dict[str, AirflowModel] = {own.kind: own}
    for name, pattern in PATTERNS.items():
        models.setdefault(name, pattern)
    solved = kept_result(scenario_id, config, air_grid(config), layout)
    if solved is not None:
        models[CFD] = CfdAirflow(solved)
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


def field(scenario_id: str, name: str, layout: str | None = None) -> FieldDocument:
    """One of a scenario's fields with one of its layouts, by default its
    own, as it is published."""
    models = _models(scenario_id, layout or DEFAULT_LAYOUT)
    model = models.get(name)
    if model is None:
        known = ", ".join(models)
        raise NotFound(f"scenario {scenario_id!r} has no field {name!r}; it has {known}")
    return model.field(f"{scenario_id}_{name}", grid(scenario_id)).document()
