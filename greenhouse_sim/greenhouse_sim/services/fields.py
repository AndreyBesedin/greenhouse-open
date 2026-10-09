"""A scenario's environment fields: its greenhouse's air, as a client draws it.

A field covers the air under the greenhouse's gutters: its floor, from its
front right corner, up to its eaves. The air in the roof's spans above them
is left out until a solver needs it (`greenhouse_sim.services.grid`).

A scenario offers every prescribed airflow pattern
(`greenhouse_sim.airflow.prescribed`): its own, as its configuration sets
it, first, and the others with their typical numbers. Then its CFD solution
(`cfd`) with the layout asked for, if one is kept that is still its
solution (`greenhouse_sim.cfd.results`). Then, if its layout places
equipment, its `climate`: its air through a climate run, with its equipment
running at the levels asked from the start, all off unless asked, then as
the commands asked set them at their moments, and its doors and vents open
as asked, at a moment of the run, which lasts up to a day
(`greenhouse_sim.climate.day`), with the sun's light at each cell
(`greenhouse_sim.solar.inside`). And last the synthetic shear the field
format is checked against.

A few recent climate runs are kept, each with the moments asked of it, so
that a later moment carries on from the latest before it.

Probes read the grid run that draws the moment asked for, every minute from
its start, beside the same run with everything off
(`greenhouse_sim.climate.probes`). The house's air as one well-mixed volume
(`greenhouse_sim.climate.house`) is read every minute from the run's
start.
"""

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Final

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.airflow.prescribed import PATTERNS
from greenhouse_sim.cfd.geometry import CfdGeometry, cfd_geometry
from greenhouse_sim.cfd.results import CfdAirflow, kept_result
from greenhouse_sim.climate.commands import Command, Schedule
from greenhouse_sim.climate.day import LONGEST_RUN_S, ClimateDay, window_start
from greenhouse_sim.climate.glazing import GlazingAt, glazed_cells
from greenhouse_sim.climate.house import HouseTrace, house_trace
from greenhouse_sim.climate.openings import OpeningsAt, opening_sites
from greenhouse_sim.climate.probes import ClimateProbes, probe_series
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument, FieldGrid
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.scenarios import (
    DEFAULT_WEATHER,
    SceneChanges,
    changed,
    equipment_levels,
    scenario,
)
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.weather.recorded import RecordedWeather
from greenhouse_sim.world.geometry import Vector3

SHEAR: Final = "shear"
CFD: Final = "cfd"
CLIMATE: Final = "climate"
# How many recent climate runs are kept.
KEPT_RUNS: Final = 8
# Probes read a climate run this often, in seconds.
PROBE_EVERY_S: Final = 60.0
# How many hexadecimal digits of its digest name a climate run.
RUN_DIGEST_LENGTH: Final = 8


class _Shear:
    """The synthetic shear, as an airflow model."""

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        return shear_field(field_id, grid)


type _Pairs = tuple[tuple[str, float], ...]
# A command as a request writes it: its moment, its actuator and its level.
type Commanded = tuple[float, str, float]


def _checked(config: ScenarioConfig, commands: Sequence[Commanded]) -> tuple[Commanded, ...]:
    """Commands to a scenario's equipment, or its doors and vents (P07.8),
    checked: one to equipment or an opening it does not have, to a level
    outside 0 to 1, or at a moment outside a run, is refused."""
    openings = {opening.opening_id for opening in config.envelope.openings}
    for _, actuator, level in commands:
        if actuator in openings:
            if not 0.0 <= level <= 1.0:
                raise InvalidRequest(f"a level runs from 0 to 1: {actuator}")
            continue
        equipment_levels(config, {actuator: level})
    outside = sorted({f"{time:g}" for time, _, _ in commands if not 0.0 <= time <= LONGEST_RUN_S})
    if outside:
        raise InvalidRequest(
            f"a command's moment lies within the run, 0 to {LONGEST_RUN_S:g} s: "
            + ", ".join(outside)
        )
    return tuple(commands)


type _RunKey = tuple[str, str, str, _Pairs, _Pairs, tuple[Commanded, ...]]
_KEPT: OrderedDict[_RunKey, ClimateDay] = OrderedDict()
_KEEPING = threading.Lock()


def forget_climate_runs() -> None:
    """Forget the kept climate runs, so that the next one asked for is run
    afresh."""
    with _KEEPING:
        _KEPT.clear()


def _climate_day(
    scenario_id: str,
    layout: str,
    weather: str,
    levels: _Pairs,
    openings: _Pairs,
    commands: tuple[Commanded, ...],
) -> ClimateDay:
    """A scenario's climate run through a day (`greenhouse_sim.climate.day`),
    with one of its layouts, under a weather, its
    equipment set to `levels` from the start and then as `commands` set it,
    and its doors and vents open as `openings` say: one of the `KEPT_RUNS`
    kept, or a new one, carrying on from those kept for the same house under
    the same weather up to where their schedules differ, as an override's
    does."""
    key = (scenario_id, layout, weather, levels, openings, commands)
    with _KEEPING:
        run = _KEPT.get(key)
        if run is not None:
            _KEPT.move_to_end(key)
            return run
        run = ClimateDay(_new_climate_run(*key))
        for (other_id, other_layout, other_weather, _, other_openings, _), other in _KEPT.items():
            if (other_id, other_layout, other_weather, other_openings) == (
                scenario_id,
                layout,
                weather,
                openings,
            ):
                run.carry_on_from(other)
        _KEPT[key] = run
        if len(_KEPT) > KEPT_RUNS:
            _KEPT.popitem(last=False)
        return run


def climate_vents(config: ScenarioConfig, geometry: CfdGeometry) -> list[Vent]:
    """A scenario's doors and vents open in `geometry`, as its climate run
    passes air through them: where each is (`greenhouse_sim.climate.openings`),
    the cells of its air's grid against it, and the opening itself, for its
    aperture at the levels a schedule opens it to."""
    sites = opening_sites(config.envelope, config.site)
    openings = {opening.opening_id: opening for opening in config.envelope.openings}
    return [
        Vent(
            site=sites[opening_id],
            cells=cells,
            axis=axis,
            outward=outward,
            opening=openings[opening_id],
        )
        for opening_id, (cells, axis, outward) in geometry.opening_cells().items()
        if opening_id in sites
    ]


def _new_climate_run(
    scenario_id: str,
    layout: str,
    weather: str,
    levels: _Pairs,
    openings: _Pairs,
    commands: tuple[Commanded, ...],
) -> ClimateRun:
    """A scenario's climate run, from its start. Its doors and vents are those
    open at the start, or opened by a command at a later moment."""
    config = changed(
        scenario(scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(openings)),
    )
    known = {opening.opening_id for opening in config.envelope.openings}
    commanded = {actuator for _, actuator, _ in commands if actuator in known}
    # Every door or vent the run opens, fully, for the cells against it.
    opened = changed(
        config, SceneChanges(openings={**dict(openings), **dict.fromkeys(commanded, 1.0)})
    )
    grid = air_grid(config)
    geometry = cfd_geometry(scenario_id, config, grid)
    # Each standing open as far as it does at the start.
    start = {opening.opening_id: opening for opening in config.envelope.openings}
    vents = [
        replace(vent, opening=start[vent.opening_id])
        for vent in climate_vents(opened, cfd_geometry(scenario_id, opened, grid))
    ]
    outside = config.run_weather()
    return ClimateRun(
        base=config.airflow,
        equipment=config.layout.equipment,
        schedule=Schedule.of(
            [
                *Schedule.from_start(dict(levels)).commands,
                *(
                    Command(time_s=time, actuator_id=actuator, level=level)
                    for time, actuator, level in commands
                ),
            ]
        ),
        settings=config.climate,
        grid=grid,
        solid=geometry.solid(),
        weather=outside,
        vents=vents,
        glazed=glazed_cells(config.envelope, grid, geometry.solid()),
        sunlight=plant_light(scenario_id, layout, weather).sunlight,
    )


class _Climate:
    """A scenario's climate, as an airflow model: its run is made, or found
    among the kept ones, only when it is drawn."""

    def __init__(
        self,
        scenario_id: str,
        layout: str,
        weather: str,
        levels: Mapping[str, float],
        openings: Mapping[str, float],
        commands: tuple[Commanded, ...],
    ):
        self.key = (
            scenario_id,
            layout,
            weather,
            tuple(sorted(levels.items())),
            tuple(sorted(openings.items())),
            commands,
        )

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        if grid != air_grid(scenario(self.key[0])):
            raise ValueError("a climate run is drawn on its own grid")
        return _climate_day(*self.key).field(field_id, time_s)


def _models(
    scenario_id: str,
    layout: str,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    weather: str = DEFAULT_WEATHER,
) -> dict[str, AirflowModel]:
    """A scenario's fields by name, with one of its layouts, its equipment at
    `levels` and then as `commands` set it, its doors and vents open as
    `openings` say, and its climate under a weather: its own airflow
    first."""
    config = changed(
        scenario(scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(openings or {})),
    )
    running = equipment_levels(config, levels or {})
    scheduled = _checked(config, commands)
    own = config.airflow
    models: dict[str, AirflowModel] = {own.kind: own}
    for name, pattern in PATTERNS.items():
        models.setdefault(name, pattern)
    solved = kept_result(scenario_id, config, air_grid(config), layout)
    if solved is not None:
        models[CFD] = CfdAirflow(solved)
    if config.layout.equipment:
        models[CLIMATE] = _Climate(scenario_id, layout, weather, running, openings or {}, scheduled)
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


def field(
    scenario_id: str,
    name: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    time_s: float = 0.0,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    weather: str | None = None,
) -> FieldDocument:
    """One of a scenario's fields with one of its layouts, by default its
    own, its equipment at `levels` and then as `commands` set it, its doors
    and vents open as `openings` say, and under a weather, by default its
    own, at `time_s` into a climate run, as it is published. A level for
    equipment it does not have, or outside 0 to 1, is refused, as are an
    opening it does not have and a moment outside a run; a weather there is
    not is not found."""
    if not 0.0 <= time_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a climate run lasts from 0 to {LONGEST_RUN_S:g} s, not {time_s:g}")
    models = _models(
        scenario_id,
        layout or DEFAULT_LAYOUT,
        levels,
        openings,
        commands,
        weather or DEFAULT_WEATHER,
    )
    model = models.get(name)
    if model is None:
        known = ", ".join(models)
        raise NotFound(f"scenario {scenario_id!r} has no field {name!r}; it has {known}")
    return model.field(f"{scenario_id}_{name}", grid(scenario_id), time_s).document()


def climate_probes(
    scenario_id: str,
    points: Sequence[tuple[float, float, float]],
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    until_s: float = 0.0,
    weather: str | None = None,
) -> ClimateProbes:
    """What probes at `points` read of the grid run that draws a scenario's
    climate at `until_s`, every `PROBE_EVERY_S` from its start to `until_s`,
    and of the same run with everything off,
    its doors and vents as asked. Asked as its climate field is, and refused
    as it is; a probe outside the house's air is refused too."""
    if not 0.0 <= until_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a climate run lasts from 0 to {LONGEST_RUN_S:g} s, not {until_s:g}")
    name = layout or DEFAULT_LAYOUT
    models = _models(scenario_id, name, levels, openings, commands, weather or DEFAULT_WEATHER)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    air = grid(scenario_id)
    probed = [Vector3(x=x, y=y, z=z) for x, y, z in points]
    outside = [point for point in probed if not air.contains(point)]
    if outside:
        named = ", ".join(f"({p.x:g}, {p.y:g}, {p.z:g})" for p in outside)
        raise InvalidRequest(f"a probe stands in the house's air, not at {named}")
    key_scenario, key_layout, key_weather, _, key_openings, _ = climate.key
    everything_off = _climate_day(key_scenario, key_layout, key_weather, (), key_openings, ())
    return probe_series(
        _climate_day(*climate.key).window(until_s),
        everything_off.window(until_s),
        probed,
        _moments(until_s, window_start(until_s)),
    )


def _moments(until_s: float, from_s: float = 0.0) -> list[float]:
    """Every `PROBE_EVERY_S` from `from_s` to `until_s`, and `until_s`."""
    first = int(from_s // PROBE_EVERY_S)
    times = [step * PROBE_EVERY_S for step in range(first, int(until_s // PROBE_EVERY_S) + 1)]
    if times[-1] < until_s:
        times.append(until_s)
    return times


def house_air(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    until_s: float = 0.0,
    weather: str | None = None,
) -> HouseTrace:
    """The house's air as one well-mixed volume (`greenhouse_sim.climate.house`)
    every `PROBE_EVERY_S` up to `until_s` of a scenario's climate run, and of
    the same run with everything off. Asked as its climate field is, and
    refused as it is."""
    if not 0.0 <= until_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a climate run lasts from 0 to {LONGEST_RUN_S:g} s, not {until_s:g}")
    name = layout or DEFAULT_LAYOUT
    models = _models(scenario_id, name, levels, openings, commands, weather or DEFAULT_WEATHER)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    key_scenario, key_layout, key_weather, _, key_openings, _ = climate.key
    return house_trace(
        _climate_day(*climate.key).house,
        _climate_day(key_scenario, key_layout, key_weather, (), key_openings, ()).house,
        _moments(until_s),
    )


def glazing(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    time_s: float = 0.0,
    weather: str | None = None,
) -> GlazingAt:
    """A scenario's glazing at `time_s` into its climate run
    (`greenhouse_sim.climate.glazing`): each wall's and roof slope's air,
    temperature and heat passed. Asked as its climate field is, and refused
    as it is."""
    if not 0.0 <= time_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a climate run lasts from 0 to {LONGEST_RUN_S:g} s, not {time_s:g}")
    name = layout or DEFAULT_LAYOUT
    models = _models(scenario_id, name, levels, openings, commands, weather or DEFAULT_WEATHER)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    return _climate_day(*climate.key).glazing_at(time_s)


def openings(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    time_s: float = 0.0,
    weather: str | None = None,
) -> OpeningsAt:
    """What a scenario's open doors and vents pass at `time_s` into its
    climate run, as the wind and the stack drive them
    (`greenhouse_sim.climate.openings`). Asked as its climate field is, and
    refused as it is."""
    if not 0.0 <= time_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a climate run lasts from 0 to {LONGEST_RUN_S:g} s, not {time_s:g}")
    name = layout or DEFAULT_LAYOUT
    models = _models(scenario_id, name, levels, openings, commands, weather or DEFAULT_WEATHER)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    return _climate_day(*climate.key).openings_at(time_s)


def air_through_a_run(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    weather: str | None = None,
) -> tuple[Callable[[float], EnvironmentField], str]:
    """A scenario's air at each moment of a run, asked as its climate field
    is, and refused as it is, with the run's identity: its climate run's, if
    its layout places equipment; otherwise its own airflow, the same at
    every moment."""
    name = layout or DEFAULT_LAYOUT
    models = _models(scenario_id, name, levels, openings, commands, weather or DEFAULT_WEATHER)
    air = grid(scenario_id)
    climate = models.get(CLIMATE)
    if isinstance(climate, _Climate):
        day = _climate_day(*climate.key)
        # A run under recorded weather is told apart by its file's content.
        under = changed(scenario(scenario_id), SceneChanges(weather=climate.key[2])).weather
        recorded = under.identity() if isinstance(under, RecordedWeather) else ""
        digest = hashlib.sha256((repr(climate.key) + recorded).encode()).hexdigest()[
            :RUN_DIGEST_LENGTH
        ]
        return (lambda time_s: day.sampled(f"{scenario_id}_{CLIMATE}", time_s)), (
            f"{scenario_id}-climate-{digest}"
        )
    config = changed(scenario(scenario_id), SceneChanges(layout=name))
    own = config.airflow.field(f"{scenario_id}_{config.airflow.kind}", air)
    return (lambda _: own), f"{scenario_id}-{config.airflow.kind}"
