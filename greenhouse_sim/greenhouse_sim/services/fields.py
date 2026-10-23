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

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.airflow.prescribed import PATTERNS
from greenhouse_sim.cfd.geometry import CfdGeometry, cfd_geometry
from greenhouse_sim.cfd.results import CfdAirflow, kept_result
from greenhouse_sim.climate.commands import (
    TARGET_EVERY_S,
    Command,
    DailyCommand,
    Schedule,
    TargetChange,
)
from greenhouse_sim.climate.day import ClimateDay, window_start
from greenhouse_sim.climate.glazing import GlazingAt, glazed_cells
from greenhouse_sim.climate.house import HouseAir, HouseTrace, house_trace
from greenhouse_sim.climate.openings import OpeningsAt, opening_sites
from greenhouse_sim.climate.probes import ClimateProbes, probe_series
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.digests import short_digest
from greenhouse_sim.domain.equipment import Target
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument, FieldGrid
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios.catalogue import Scenarios
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.kept_states import House, KeptState, agreeing
from greenhouse_sim.services.runs import Commanded, RunRequest, checked_moment, checked_window
from greenhouse_sim.services.scenarios import (
    DEFAULT_WEATHER,
    SceneChanges,
    changed,
    equipment_levels,
    layout_name,
    scenario,
)
from greenhouse_sim.services.stores import Store, digest_label
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.weather.recorded import RecordedWeather
from greenhouse_sim.world.geometry import Vector3

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

SHEAR: Final = "shear"
CFD: Final = "cfd"
CLIMATE: Final = "climate"
# How many recent climate runs are kept.
KEPT_RUNS: Final = 8
# A heating setpoint a run may be given (#274): above freezing, and below
# what a crop survives.
SETPOINT_RANGE_C: Final = (0.0, 40.0)
# Probes read a climate run this often, in seconds.
PROBE_EVERY_S: Final = 60.0
# How many hexadecimal digits of its digest name a climate run.
RUN_DIGEST_LENGTH: Final = 8


class _Shear:
    """The synthetic shear, as an airflow model."""

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        return shear_field(field_id, grid)


type _Pairs = tuple[tuple[str, float], ...]


def _checked(
    config: ScenarioConfig,
    commands: Sequence[Commanded],
    daily: Sequence[Commanded] | None = None,
) -> tuple[Commanded, ...]:
    """Commands to a scenario's equipment, or its doors and vents (P07.8),
    checked: one to equipment or an opening it does not have, to a level
    outside 0 to 1, or at a moment outside a run, is refused. A daily
    command, its time of day for its moment (P09.2), is checked as the
    others are, and refused at a time of day outside a day; it becomes a
    command at that time on each of the run's days, before the others
    (`greenhouse_sim.climate.commands`). Without daily commands of its own,
    a run gives its scenario's (P09.4)."""
    if daily is None:
        daily = [
            (command.time_of_day_s, command.actuator_id, command.level) for command in config.daily
        ]
    openings = {opening.opening_id for opening in config.envelope.openings}
    for _, actuator, level in (*daily, *commands):
        if actuator in openings:
            if not 0.0 <= level <= 1.0:
                raise InvalidRequest(f"a level runs from 0 to 1: {actuator}")
            continue
        equipment_levels(config, {actuator: level})
    length = config.run_length_s()
    outside = sorted({f"{time:.15g}" for time, _, _ in commands if not 0.0 <= time <= length})
    if outside:
        raise InvalidRequest(
            f"a command's moment lies within the run, 0 to {length:.15g} s: " + ", ".join(outside)
        )
    late = sorted({f"{time:.15g}" for time, _, _ in daily if not 0.0 <= time < DAY_S})
    if late:
        raise InvalidRequest(
            f"a daily command's time of day lies from 0 to {DAY_S:.15g} s, before the next "
            "midnight: " + ", ".join(late)
        )
    each_day = tuple(
        (command.time_s, command.actuator_id, command.level)
        for time, actuator, level in daily
        for command in DailyCommand(time_of_day_s=time, actuator_id=actuator, level=level).through(
            config.duration_days
        )
    )
    return (*each_day, *commands)


def _schedule(
    levels: _Pairs, commands: tuple[Commanded, ...], targets: tuple[Commanded, ...] = ()
) -> Schedule:
    """A climate run's schedule: its equipment's levels from the start, then
    its commands, and its target changes, checked."""
    return Schedule.of(
        [
            *Schedule.from_start(dict(levels)).commands,
            *(
                Command(time_s=time, actuator_id=actuator, level=level)
                for time, actuator, level in commands
            ),
        ],
        [
            TargetChange(time_s=time, target=Target(target), value_c=value)
            for time, target, value in targets
        ],
    )


def _checked_targets(config: ScenarioConfig, targets: Sequence[Commanded]) -> tuple[Commanded, ...]:
    """A run's target changes (#274), checked: one to a target its
    scenario's controller does not have, outside `SETPOINT_RANGE_C`, at a
    moment outside a run, or not on the minute, is refused. In the order
    they apply, by moment and as given at a moment, so that the same
    changes asked for in another order make the same run."""
    if not targets:
        return ()
    if config.thermostat is None:
        raise InvalidRequest(f"{config.greenhouse_id} has no heating loop whose target to change")
    names = ", ".join(target.value for target in Target)
    low, high = SETPOINT_RANGE_C
    length = config.run_length_s()
    for time, target, value in targets:
        if target not in Target:
            raise InvalidRequest(f"a target is one of {names}, not {target!r}")
        if not low <= value <= high:
            raise InvalidRequest(
                f"a heating setpoint lies from {low:.15g} to {high:.15g} °C, not {value:.15g}"
            )
        if not 0.0 <= time <= length or time % TARGET_EVERY_S:
            raise InvalidRequest(
                f"a target changes on the minute, within the run, 0 to {length:.15g} s, not at "
                f"{time:.15g} s"
            )
    return tuple(sorted(targets, key=lambda change: change[0]))


def run_schedule(catalogue: Scenarios, run: RunRequest) -> Schedule:
    """The schedule a run's climate is given, asked for and checked as its
    climate field is: its equipment at its levels from the start, then as
    its daily commands and its commands set it."""
    config = changed(
        catalogue,
        scenario(catalogue, run.scenario_id),
        SceneChanges(layout=run.layout or DEFAULT_LAYOUT),
    )
    running = equipment_levels(config, run.levels)
    return _schedule(
        tuple(sorted(running.items())),
        _checked(config, run.commands, run.daily),
        _checked_targets(config, run.targets),
    )


# What tells one climate run from another: its scenario, layout and weather,
# its equipment's levels and its doors' and vents' from the start, its
# commands after it, and its target changes.
type RunKey = tuple[str, str, str, _Pairs, _Pairs, tuple[Commanded, ...], tuple[Commanded, ...]]


def run_label(key: RunKey) -> str:
    """A kept run's name in the log: its scenario, and a digest of the rest."""
    return f"{key[0]} {digest_label(key)}"


def new_store() -> Store[RunKey, ClimateDay]:
    """A simulator's climate runs: the latest `KEPT_RUNS` (decision 0048)."""
    return Store("climate runs", KEPT_RUNS, label=run_label)


def _climate_day(simulator: Simulator, key: RunKey) -> ClimateDay:
    """The climate run through a day (`greenhouse_sim.climate.day`) that `key`
    names: a scenario with one of its layouts, under a weather, its equipment
    set to its levels from the start and then as its commands set it, its
    targets changed as its target changes do, and its doors and vents open as
    its openings say: one of the `KEPT_RUNS` kept, or a new one, carrying on
    from those kept for the same house under the same weather up to where
    their schedules differ, as an override's does."""

    def make(others: list[tuple[RunKey, ClimateDay]]) -> ClimateDay:
        run = ClimateDay(_new_climate_run(simulator, key))
        for _, other in others:
            run.carry_on_from(other)
        taken_over = agreeing(simulator, house_of(key), run.run.schedule)
        for state in taken_over:
            for moment, air in state.airs():
                run.house.seed(moment, air)
        if taken_over:
            logger.info(
                "climate runs: %s takes over the kept states of days %s",
                run_label(key),
                ", ".join(str(state.day) for state in taken_over),
                extra={
                    "store": simulator.climate_runs.name,
                    "event": "taken over",
                    "label": run_label(key),
                },
            )
        return run

    return simulator.climate_runs.made_once(
        key, make, lambda other: house_of(other) == house_of(key)
    )


def house_of(key: RunKey) -> House:
    """A run's house, as its key names it: its scenario, layout and weather,
    and its doors and vents open from the start. Runs of the same house are
    the same air until their schedules differ."""
    scenario_id, layout, weather, _, openings, *_ = key
    return scenario_id, layout, weather, openings


def off_levels(catalogue: Scenarios, scenario_id: str) -> dict[str, float]:
    """The levels that switch off, from the start, what a scenario's run
    would otherwise run by itself: its thermostat's heater, at 0
    (`climate.thermostat`). With no daily commands and no others, its run
    has everything off."""
    thermostat = scenario(catalogue, scenario_id).thermostat
    return {} if thermostat is None else {thermostat.actuator_id: 0.0}


def _everything_off(simulator: Simulator, key: RunKey) -> ClimateDay:
    """The run `key` names with everything off: its house, under its
    weather, its doors and vents as open from the start, and nothing run."""
    scenario_id, layout, weather, _, openings, *_ = key
    off = tuple(sorted(off_levels(simulator.catalogue, scenario_id).items()))
    return _climate_day(simulator, (scenario_id, layout, weather, off, openings, (), ()))


def climate_run(simulator: Simulator, run: RunRequest) -> tuple[RunKey, ClimateDay]:
    """A run's climate, asked for and checked as its climate field is, with
    what tells it from another: the air its crop lives in, whether or not
    its layout places equipment."""
    name = run.layout or DEFAULT_LAYOUT
    under = run.weather or DEFAULT_WEATHER
    config = changed(
        simulator.catalogue,
        scenario(simulator.catalogue, run.scenario_id),
        SceneChanges(layout=name, weather=under, openings=dict(run.openings)),
    )
    key = (
        run.scenario_id,
        layout_name(name),
        under,
        tuple(sorted(equipment_levels(config, run.levels).items())),
        tuple(sorted(run.openings.items())),
        _checked(config, run.commands, run.daily),
        _checked_targets(config, run.targets),
    )
    return key, _climate_day(simulator, key)


def seed_kept_climate_runs(simulator: Simulator, state: KeptState) -> None:
    """Give a kept state to the climate runs kept that agree with it."""
    for key, run in simulator.climate_runs.values():
        if state.agrees(house_of(key), run.run.schedule):
            for moment, air in state.airs():
                run.house.seed(moment, air)


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


def _new_climate_run(simulator: Simulator, key: RunKey) -> ClimateRun:
    """The climate run `key` names, from its start. Its doors and vents are
    those open at the start, or opened by a command at a later moment."""
    scenario_id, layout, weather, levels, openings, commands, targets = key
    config = changed(
        simulator.catalogue,
        scenario(simulator.catalogue, scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(openings)),
    )
    known = {opening.opening_id for opening in config.envelope.openings}
    commanded = {actuator for _, actuator, _ in commands if actuator in known}
    # Every door or vent the run opens, fully, for the cells against it.
    opened = changed(
        simulator.catalogue,
        config,
        SceneChanges(openings={**dict(openings), **dict.fromkeys(commanded, 1.0)}),
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
        schedule=_schedule(levels, commands, targets),
        settings=config.climate,
        grid=grid,
        solid=geometry.solid(),
        weather=outside,
        vents=vents,
        glazed=glazed_cells(config.envelope, grid, geometry.solid()),
        sunlight=plant_light(simulator, scenario_id, layout, weather).sunlight,
        thermostat=config.thermostat,
    )


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
        return _climate_day(self._simulator, self.key).field(field_id, time_s)


def _models(simulator: Simulator, run: RunRequest) -> dict[str, AirflowModel]:
    """A run's fields by name: its scenario's with one of its layouts, its
    equipment at its levels and then as its daily commands and its commands
    set it, its doors and vents open as it asks, and its climate under a
    weather; its own airflow first."""
    layout = run.layout or DEFAULT_LAYOUT
    weather = run.weather or DEFAULT_WEATHER
    config = changed(
        simulator.catalogue,
        scenario(simulator.catalogue, run.scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(run.openings)),
    )
    running = equipment_levels(config, run.levels)
    scheduled = _checked(config, run.commands, run.daily)
    targets = _checked_targets(config, run.targets)
    own = config.airflow
    models: dict[str, AirflowModel] = {own.kind: own}
    for name, pattern in PATTERNS.items():
        models.setdefault(name, pattern)
    solved = kept_result(run.scenario_id, config, air_grid(config), layout)
    if solved is not None:
        models[CFD] = CfdAirflow(solved)
    if config.layout.equipment:
        models[CLIMATE] = _Climate(
            simulator,
            scenario_id=run.scenario_id,
            layout=layout_name(layout),
            weather=weather,
            levels=running,
            openings=run.openings,
            commands=scheduled,
            targets=targets,
        )
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


def climate_probes(
    simulator: Simulator,
    run: RunRequest,
    points: Sequence[tuple[float, float, float]],
    until_s: float = 0.0,
) -> ClimateProbes:
    """What probes at `points` read of the grid run that draws a run's
    climate at `until_s`, every `PROBE_EVERY_S` from its start to `until_s`,
    and of the same run with everything off, its doors and vents as asked.
    Asked as its climate field is, and refused as it is; a probe outside the
    house's air is refused too."""
    scenario_id = run.scenario_id
    checked_moment(scenario(simulator.catalogue, scenario_id), until_s)
    models = _models(simulator, run)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    air = grid(simulator.catalogue, scenario_id)
    probed = [Vector3(x=x, y=y, z=z) for x, y, z in points]
    outside = [point for point in probed if not air.contains(point)]
    if outside:
        named = ", ".join(f"({p.x:g}, {p.y:g}, {p.z:g})" for p in outside)
        raise InvalidRequest(f"a probe stands in the house's air, not at {named}")
    return probe_series(
        _climate_day(simulator, climate.key).window(until_s),
        _everything_off(simulator, climate.key).window(until_s),
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
    simulator: Simulator, run: RunRequest, until_s: float = 0.0, from_s: float | None = None
) -> HouseTrace:
    """The house's air as one well-mixed volume (`greenhouse_sim.climate.house`)
    every `PROBE_EVERY_S` from `from_s`, by default the start of the day
    `until_s` belongs to (`services.runs`), to `until_s` of a run's climate,
    and of the same run with everything off. Asked as its climate field is,
    and refused as it is."""
    scenario_id = run.scenario_id
    first = checked_window(scenario(simulator.catalogue, scenario_id), from_s, until_s)
    models = _models(simulator, run)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    return house_trace(
        _climate_day(simulator, climate.key).house,
        _everything_off(simulator, climate.key).house,
        _moments(until_s, first),
    )


def house_air_at(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> HouseAir | None:
    """The house's air as one well-mixed volume at a moment of a run's
    climate, asked as its climate field is and refused as it is; None for a
    scenario without equipment, which has no climate run. Unlike
    `house_air`, it works out nothing of the same run all off."""
    checked_moment(scenario(simulator.catalogue, run.scenario_id), time_s)
    models = _models(simulator, run)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        return None
    return _climate_day(simulator, climate.key).house.air_at(time_s)


class ThermostatAt(BaseModel):
    """A run's thermostat at a moment (`climate.thermostat`): the heater it
    runs, the temperature it heats the house's air to then, its setpoints by
    day and by night then, as the run's target changes have left them
    (#274), and whether it runs the heater then, or a command to the heater
    has taken it over."""

    model_config = ConfigDict(frozen=True)

    actuator_id: str
    setpoint_c: float
    day_c: float
    night_c: float
    runs: bool


class EquipmentAt(BaseModel):
    """A run's equipment at a moment: each piece's level, as its commands set
    it and its thermostat runs its heater, and the thermostat, if it has
    one."""

    model_config = ConfigDict(frozen=True)

    time_s: float
    levels: dict[str, float]
    thermostat: ThermostatAt | None


def equipment_at(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> EquipmentAt:
    """A run's equipment at a moment of its climate, asked as its climate
    field is and refused as it is: none for a scenario without equipment,
    which has no climate run."""
    checked_moment(scenario(simulator.catalogue, run.scenario_id), time_s)
    models = _models(simulator, run)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        return EquipmentAt(time_s=time_s, levels={}, thermostat=None)
    worked = _climate_day(simulator, climate.key).run
    thermostat = worked.thermostat
    targets = worked.schedule.targets_at(time_s)
    return EquipmentAt(
        time_s=time_s,
        levels=worked.levels_at(time_s),
        thermostat=None
        if thermostat is None
        else ThermostatAt(
            actuator_id=thermostat.actuator_id,
            setpoint_c=thermostat.setpoint_c(time_s, targets),
            day_c=thermostat.setpoints_c(targets)[0],
            night_c=thermostat.setpoints_c(targets)[1],
            runs=worked.thermostat_governs(time_s),
        ),
    )


def glazing(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> GlazingAt:
    """A run's glazing at `time_s` into its climate
    (`greenhouse_sim.climate.glazing`): each wall's and roof slope's air,
    temperature and heat passed. Asked as its climate field is, and refused
    as it is."""
    scenario_id = run.scenario_id
    checked_moment(scenario(simulator.catalogue, scenario_id), time_s)
    models = _models(simulator, run)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    return _climate_day(simulator, climate.key).glazing_at(time_s)


def openings(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> OpeningsAt:
    """What a run's open doors and vents pass at `time_s` into its climate,
    as the wind and the stack drive them (`greenhouse_sim.climate.openings`).
    Asked as its climate field is, and refused as it is."""
    scenario_id = run.scenario_id
    checked_moment(scenario(simulator.catalogue, scenario_id), time_s)
    models = _models(simulator, run)
    climate = models.get(CLIMATE)
    if not isinstance(climate, _Climate):
        raise NotFound(f"scenario {scenario_id!r} has no climate: it has no equipment")
    return _climate_day(simulator, climate.key).openings_at(time_s)


def air_through_a_run(
    simulator: Simulator, run: RunRequest
) -> tuple[Callable[[float], EnvironmentField], str]:
    """A run's air at each of its moments, asked as its climate field is,
    and refused as it is, with the run's identity: its climate's, if its
    layout places equipment; otherwise its own airflow, the same at every
    moment."""
    scenario_id = run.scenario_id
    name = run.layout or DEFAULT_LAYOUT
    models = _models(simulator, run)
    air = grid(simulator.catalogue, scenario_id)
    climate = models.get(CLIMATE)
    # A run of a scenario is told apart by what it is made of, whatever
    # drives its air: a manifest or a layout changed, such as its weather or
    # its heater, makes another run.
    if isinstance(climate, _Climate):
        day = _climate_day(simulator, climate.key)
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
        digest = _digest(repr(named) + recorded + config.model_dump_json())
        return (lambda time_s: day.sampled(f"{scenario_id}_{CLIMATE}", time_s)), (
            f"{scenario_id}-climate-{digest}"
        )
    config = changed(
        simulator.catalogue, scenario(simulator.catalogue, scenario_id), SceneChanges(layout=name)
    )
    own = config.airflow.field(f"{scenario_id}_{config.airflow.kind}", air)
    digest = _digest(config.model_dump_json())
    return (lambda _: own), f"{scenario_id}-{config.airflow.kind}-{digest}"


def _digest(told: str) -> str:
    """What tells one run from another, shortened."""
    return short_digest(told, RUN_DIGEST_LENGTH)
