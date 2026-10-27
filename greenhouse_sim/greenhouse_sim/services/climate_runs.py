"""A scenario's climate runs, as a simulator keeps them.

A climate run (`greenhouse_sim.climate.day`) is a house under a weather,
its equipment running at the levels asked from the start, all off unless
asked, then as the commands asked set them at their moments, its targets
changed as its target changes ask, and its doors and vents open as asked.
What it is asked is checked here, and what tells one run from another, its
key, is made from it.

A few recent climate runs are kept, each with the moments asked of it, so
that a later moment carries on from the latest before it, and a new run
carries on from those of the same house up to where their schedules
differ.
"""

import logging
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Final

from greenhouse_protocol.actions import HEATING_SETPOINT_RANGE_C

from greenhouse_sim.cfd.geometry import CfdGeometry, cfd_geometry
from greenhouse_sim.climate.commands import (
    TARGET_EVERY_S,
    Command,
    DailyCommand,
    Schedule,
    TargetChange,
)
from greenhouse_sim.climate.day import DAYS, ClimateDay
from greenhouse_sim.climate.glazing import glazed_cells
from greenhouse_sim.climate.openings import opening_sites
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.equipment import Target
from greenhouse_sim.scenarios.catalogue import Scenarios
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.kept_states import House, KeptState, agreeing
from greenhouse_sim.services.runs import Commanded, RunPlan, RunRequest
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

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

# How many recent climate runs are kept.
KEPT_RUNS: Final = 8
# A heating setpoint a run may be given (#274): above freezing, and below
# what a crop survives; the protocol's, wherever a setpoint is set.
SETPOINT_RANGE_C: Final = HEATING_SETPOINT_RANGE_C


type _Pairs = tuple[tuple[str, float], ...]


def checked_commands(
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


def checked_targets(config: ScenarioConfig, targets: Sequence[Commanded]) -> tuple[Commanded, ...]:
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
        _keeps_the_dead_band(config, target, value)
        if not 0.0 <= time <= length or time % TARGET_EVERY_S:
            raise InvalidRequest(
                f"a target changes on the minute, within the run, 0 to {length:.15g} s, not at "
                f"{time:.15g} s"
            )
    return tuple(sorted(targets, key=lambda change: change[0]))


def _keeps_the_dead_band(config: ScenarioConfig, target: str, value_c: float) -> None:
    """Refuse a heating setpoint changed to `value_c` that would leave the
    heater on while the vents open for heat: in its period, the vents'
    first stage closes above the temperature the heater switches off at by
    at least the controller's dead band, as its configuration's do
    (`climate.control`)."""
    control = config.control
    if control is None or control.heating is None or control.venting is None:
        return
    by_day = target == Target.HEATING_DAY
    closes_c = control.venting.first_closes_below_c(control.venting.setpoint_c(by_day))
    most_c = closes_c - control.dead_band_c - control.heating.band_c / 2
    if value_c > most_c:
        period = "by day" if by_day else "by night"
        raise InvalidRequest(
            f"a heating setpoint {period} of {value_c:.15g} °C leaves less than the dead band "
            f"of {control.dead_band_c:.15g} °C below where the vents' first stage closes, "
            f"{closes_c:.15g} °C: at most {most_c:.15g} °C"
        )


def checked_actions(config: ScenarioConfig, plan: RunPlan) -> None:
    """A plan's levels and target changes, checked as `run_schedule` checks
    a run's, against a scenario as its run changes it, leaving out the
    scenario's daily commands, which its run checks: a gateway checks each
    action as it is given, and a season of daily commands worked out for
    each would cost every action as much as a whole run's schedule."""
    checked_commands(config, plan.commanded(), daily=())
    checked_targets(config, plan.targeted())


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
        checked_commands(config, run.plan.commanded(), run.plan.daily_commanded()),
        checked_targets(config, run.plan.targeted()),
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


def climate_day(simulator: Simulator, key: RunKey) -> ClimateDay:
    """The climate run through a day (`greenhouse_sim.climate.day`) that `key`
    names, by its scenario's house air's model: a scenario with one of its
    layouts, under a weather, its equipment
    set to its levels from the start and then as its commands set it, its
    targets changed as its target changes do, and its doors and vents open as
    its openings say: one of the `KEPT_RUNS` kept, or a new one, carrying on
    from those kept for the same house under the same weather up to where
    their schedules differ, as an override's does."""

    # A day of its house air's model: cell by cell beside the whole house,
    # or the whole house alone (P14.6).
    day = DAYS[scenario(simulator.catalogue, key[0]).climate.kind]

    def make(others: list[tuple[RunKey, ClimateDay]]) -> ClimateDay:
        run = day(_new_climate_run(simulator, key))
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
    would otherwise run by itself: each piece of equipment its controller
    runs, at 0 (`climate.control`): its heater, its fans and its
    dehumidifier. With no daily commands and no others, and its
    controller's vents held where they start (`everything_off`), its run has
    everything off."""
    config = scenario(catalogue, scenario_id)
    if config.control is None:
        return {}
    openings = {opening.opening_id for opening in config.envelope.openings}
    return {device: 0.0 for device in config.control.runs() if device not in openings}


def everything_off(simulator: Simulator, key: RunKey) -> ClimateDay:
    """The run `key` names with everything off: its house, under its
    weather, its doors and vents as open from the start, its controller's
    vents held there by commands from the start, and nothing run."""
    scenario_id, layout, weather, _, openings, *_ = key
    off = tuple(sorted(off_levels(simulator.catalogue, scenario_id).items()))
    config = scenario(simulator.catalogue, scenario_id)
    venting = None if config.control is None else config.control.venting
    start = {opening.opening_id: opening.opening for opening in config.envelope.openings}
    started = start | dict(openings)
    held = () if venting is None else tuple((0.0, vent, started[vent]) for vent in venting.vents)
    return climate_day(simulator, (scenario_id, layout, weather, off, openings, held, ()))


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
        checked_commands(config, run.plan.commanded(), run.plan.daily_commanded()),
        checked_targets(config, run.plan.targeted()),
    )
    return key, climate_day(simulator, key)


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
    those open at the start, opened by a command at a later moment, or run
    by its controller's venting loop (P11.2)."""
    scenario_id, layout, weather, levels, openings, commands, targets = key
    config = changed(
        simulator.catalogue,
        scenario(simulator.catalogue, scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(openings)),
    )
    known = {opening.opening_id for opening in config.envelope.openings}
    commanded = {actuator for _, actuator, _ in commands if actuator in known}
    if config.control is not None and config.control.venting is not None:
        commanded |= set(config.control.venting.vents)
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
        settings=config.climate.run_settings(),
        grid=grid,
        solid=geometry.solid(),
        weather=outside,
        vents=vents,
        glazed=glazed_cells(config.envelope, grid, geometry.solid()),
        sunlight=plant_light(simulator, scenario_id, layout, weather).sunlight,
        control=config.control,
    )
