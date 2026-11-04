"""A scenario's environment fields: its greenhouse's air, as a client draws it.

A field covers the air under the greenhouse's gutters: its floor, from its
front right corner, up to its eaves. The air in the roof's spans above them
is left out until a solver needs it (`greenhouse_sim.services.grid`).

A scenario offers every prescribed airflow pattern
(`greenhouse_sim.airflow.prescribed`): its own, as its configuration sets
it, first, and the others with their typical numbers. Then its CFD solution
(`cfd`) with the layout asked for, if one is kept that is still its
solution (`greenhouse_sim.cfd.results`). Then its `climate`: its air through
a climate run, with its equipment, if its layout places any, running at the
levels asked from the start, all off unless asked, then as the commands
asked set them at their moments, and its doors and vents open as asked, at a
moment of the run, which lasts up to a day (`greenhouse_sim.climate.day`),
with the sun's light at each cell (`greenhouse_sim.solar.inside`). And last
the synthetic shear the field format is checked against.

Every house has a climate run, the air its crop lives in. What its sensors
read, and what names its run, depend on its layout, though
(`air_through_a_run`): a layout that places no equipment is sensed in its own
airflow, and named by it.

The climate runs themselves are kept by `greenhouse_sim.services.climate_runs`,
and what a run's climate reads at its moments is given by
`greenhouse_sim.services.climate_readings`.
"""

import json
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.airflow.prescribed import PATTERNS
from greenhouse_sim.cfd.results import CfdAirflow, kept_result
from greenhouse_sim.digests import short_digest
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument, FieldGrid
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios.catalogue import Scenarios
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.scenarios.registry import models_run
from greenhouse_sim.services.climate_runs import (
    RunKey,
    checked_commands,
    checked_targets,
    climate_day,
)
from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.runs import (
    Commanded,
    RunRequest,
    checked_crop_plan,
    checked_moment,
)
from greenhouse_sim.services.scenarios import (
    SceneChanges,
    changed,
    equipment_levels,
    layout_name,
    scenario,
    with_weather,
)
from greenhouse_sim.weather.recorded import RecordedWeather

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

SHEAR: Final = "shear"
CFD: Final = "cfd"
CLIMATE: Final = "climate"
# How many hexadecimal digits of its digest name a climate run.
RUN_DIGEST_LENGTH: Final = 8


class _Shear:
    """The synthetic shear, as an airflow model."""

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        return shear_field(field_id, grid)


class _Climate:
    """A scenario's climate, as an airflow model: its run is made, or found
    among the kept ones, only when it is drawn."""

    def __init__(
        self,
        simulator: Simulator,
        *,
        scenario_id: str,
        layout: str,
        weather: str,
        levels: Mapping[str, float],
        openings: Mapping[str, float],
        commands: tuple[Commanded, ...],
        targets: tuple[Commanded, ...] = (),
    ):
        self._simulator = simulator
        self.key: RunKey = (
            scenario_id,
            layout,
            weather,
            tuple(sorted(levels.items())),
            tuple(sorted(openings.items())),
            commands,
            targets,
        )

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        if grid != air_grid(scenario(self._simulator.catalogue, self.key[0])):
            raise ValueError("a climate run is drawn on its own grid")
        return climate_day(self._simulator, self.key).field(field_id, time_s)


def _asked(simulator: Simulator, run: RunRequest) -> tuple[ScenarioConfig, _Climate]:
    """A run's scenario with one of its layouts, under a weather, its doors
    and vents open as it asks, and its climate, its equipment at its levels
    and then as its daily commands and its commands set it, all checked."""
    layout = run.layout or DEFAULT_LAYOUT
    weather = run.weather_name(simulator.catalogue)
    config = changed(
        simulator.catalogue,
        scenario(simulator.catalogue, run.scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(run.openings)),
    )
    running = equipment_levels(config, run.levels)
    scheduled = checked_commands(config, run.plan.commanded(), run.plan.daily_commanded())
    targets = checked_targets(config, run.plan.targeted())
    return config, _Climate(
        simulator,
        scenario_id=run.scenario_id,
        layout=layout_name(layout),
        weather=weather,
        levels=running,
        openings=run.openings,
        commands=scheduled,
        targets=targets,
    )


def _models(simulator: Simulator, run: RunRequest) -> dict[str, AirflowModel]:
    """A run's fields by name: its scenario's as it asks for it, and its
    climate; its own airflow first."""
    config, climate = _asked(simulator, run)
    own = config.airflow
    models: dict[str, AirflowModel] = {own.kind: own}
    for name, pattern in PATTERNS.items():
        models.setdefault(name, pattern)
    solved = kept_result(run.scenario_id, config, air_grid(config), run.layout or DEFAULT_LAYOUT)
    if solved is not None:
        models[CFD] = CfdAirflow(solved)
    models[CLIMATE] = climate
    models[SHEAR] = _Shear()
    return models


def field_names(simulator: Simulator, scenario_id: str, layout: str | None = None) -> list[str]:
    """The fields a scenario offers with one of its layouts, by default its
    own, its own airflow first. Only its CFD solution depends on the
    layout."""
    return list(_models(simulator, RunRequest(scenario_id, layout=layout)))


def configured(catalogue: Scenarios, scenario_id: str) -> str:
    """The name of a scenario's own airflow."""
    return scenario(catalogue, scenario_id).airflow.kind


class FieldNames(BaseModel):
    """The fields a scenario offers with one of its layouts, its own airflow
    first, and the name of its own airflow."""

    model_config = ConfigDict(frozen=True)

    fields: list[str]
    configured: str


def offered_fields(simulator: Simulator, scenario_id: str, layout: str | None = None) -> FieldNames:
    """The fields a scenario offers with one of its layouts, and its own
    airflow, as the viewer lists them to choose from."""
    return FieldNames(
        fields=field_names(simulator, scenario_id, layout),
        configured=configured(simulator.catalogue, scenario_id),
    )


def grid(catalogue: Scenarios, scenario_id: str) -> FieldGrid:
    """The grid a scenario's fields cover: its greenhouse's air under the
    gutters."""
    return air_grid(scenario(catalogue, scenario_id))


def field(simulator: Simulator, run: RunRequest, name: str, time_s: float = 0.0) -> FieldDocument:
    """One of a run's fields at `time_s` into it, as it is published: its
    scenario's with one of its layouts, by default its own, its equipment at
    its levels and then as its commands and daily commands set it, its doors
    and vents open as it asks, under a weather, by default its own. A level
    for equipment it does not have, or outside 0 to 1, is refused, as are an
    opening it does not have and a moment outside a run; a weather there is
    not is not found."""
    scenario_id = run.scenario_id
    checked_moment(scenario(simulator.catalogue, scenario_id), time_s)
    models = _models(simulator, run)
    model = models.get(name)
    if model is None:
        known = ", ".join(models)
        raise NotFound(f"scenario {scenario_id!r} has no field {name!r}; it has {known}")
    return model.field(
        f"{scenario_id}_{name}", grid(simulator.catalogue, scenario_id), time_s
    ).document()


def climate_key(simulator: Simulator, run: RunRequest) -> RunKey:
    """What names a run's climate, asked for and checked as its climate
    field is."""
    return _asked(simulator, run)[1].key


def air_through_a_run(
    simulator: Simulator, run: RunRequest
) -> tuple[Callable[[float], EnvironmentField], str]:
    """A run's air at each of its moments, as its sensors read it, asked as
    its climate field is, and refused as it is, with the run's identity: its
    climate's, if its layout places equipment or its scenario is not packaged;
    otherwise, a packaged layout that places none, its own airflow, the same at
    every moment, however its climate run stands. The packaged scenarios' run
    ids and what was recorded under them rest on that choice, so it tests the
    layout and where the scenario came from, not whether the run has a climate,
    which every run has."""
    scenario_id = run.scenario_id
    name = run.layout or DEFAULT_LAYOUT
    asked, climate = _asked(simulator, run)
    air = grid(simulator.catalogue, scenario_id)
    entry = simulator.catalogue.entry(scenario_id)
    packaged = entry is not None and entry.packaged
    # A run of a scenario is told apart by what it is made of, whatever
    # drives its air: a manifest or a layout changed, such as its weather or
    # its heater, makes another run.
    if asked.layout.equipment or not packaged:
        day = climate_day(simulator, climate.key)
        config = changed(
            simulator.catalogue,
            scenario(simulator.catalogue, scenario_id),
            SceneChanges(layout=climate.key[1], weather=climate.key[2]),
        )
        # A run under recorded weather is told apart by its file's content.
        under = config.weather
        recorded = under.identity() if isinstance(under, RecordedWeather) else ""
        # A run whose targets are its scenario's own is named as it was before
        # runs had target changes (#274), so its identity stays.
        named = climate.key if climate.key[-1] else climate.key[:-1]
        digest = _digest(
            repr(named)
            + recorded
            + _models_told(config)
            + config.model_dump_json()
            + _cropped(config, run)
        )
        return (lambda time_s: day.sampled(f"{scenario_id}_{CLIMATE}", time_s)), (
            f"{scenario_id}-climate-{digest}"
        )
    # Its airflow is the same under any weather, so the weather named is not
    # applied (nor does it make another run), but the seed is: it draws the
    # sensors' readings and the crop's, which another seed makes another run.
    config = changed(
        simulator.catalogue, scenario(simulator.catalogue, scenario_id), SceneChanges(layout=name)
    ).model_copy(
        update={
            "random_seed": with_weather(
                scenario(simulator.catalogue, scenario_id), run.weather_name(simulator.catalogue)
            ).random_seed
        }
    )
    own = config.airflow.field(f"{scenario_id}_{config.airflow.kind}", air)
    digest = _digest(_models_told(config) + config.model_dump_json() + _cropped(config, run))
    return (lambda _: own), f"{scenario_id}-{config.airflow.kind}-{digest}"


def _models_told(config: ScenarioConfig) -> str:
    """What tells a run's models from another's: each part's model and its
    version (P14.2, decision 0054), so that a model's numbers changed, its
    version with them, make another run."""
    runs = {part.value: run.model_dump() for part, run in models_run(config).items()}
    return json.dumps(runs, sort_keys=True)


def _cropped(config: ScenarioConfig, run: RunRequest) -> str:
    """What tells a run with crop actions of its own (P13.5) from one
    without: its crop actions, checked, by their moments, those at one
    moment in the order they apply; nothing for a run without, whose
    identity stays as it was before runs had them."""
    cropped = sorted(run.plan.cropped(), key=lambda each: each.at_s)
    if not cropped:
        return ""
    checked_crop_plan(config, run.plan)
    return json.dumps([[each.at_s, each.action.model_dump(mode="json")] for each in cropped])


def _digest(told: str) -> str:
    """What tells one run from another, shortened."""
    return short_digest(told, RUN_DIGEST_LENGTH)
