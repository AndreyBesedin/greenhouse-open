"""The evaluator's instruments (P25.2, decision 0082): what an episode's run
truly did to the house, read once its policy has stopped, from the run as
carried out (`experiment.carry_out_episode`).

- **The house's air through time** (`house_air`): every minute from the
  run's start, the whole house's air (`climate.house`), the air its loops
  decide from and its crop lives in: temperature, relative humidity and
  CO₂.
- **The heat given** (`heat_given`): the heaters' heat to the air from the
  house's own count, `HouseAir.heated_j`, over any stretch to the second,
  of which the hourly heat records are a rounding (`services.heat_log`).
- **The equipment's states through time** (`equipment_states`): each
  device's level from the run's start, and each switch with its moment,
  its level and what set it: its controller's loop, at the moment the air
  reaches the loop's edge (`WholeHouse.controlled_through`), or a command,
  at its own (`climate.commands`).
- **The harvest** (`harvest`): the run's harvest events, from its crop work
  and its plan's harvests, the crop model's prediction (decision 0081).

`Instruments` reads them for one episode, each the first time it is asked
for, and gives a measure's source (`greenhouse_protocol.benchmark.
FromInstrument`) as the series its arithmetic takes
(`greenhouse_protocol.measuring`).

Nothing here reaches a policy: not its port, the consumer interface or its
capability context, whose modules import none of the evaluation
(`tests/test_dependencies.py`). People read the same truth through the
local API (decision 0036).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from itertools import pairwise
from typing import Final

from greenhouse_protocol.actions import Harvest
from greenhouse_protocol.benchmark import FromInstrument, Instrument
from greenhouse_protocol.enums import EventType
from greenhouse_protocol.measuring import Sample
from greenhouse_protocol.outcome import Harvested

from greenhouse_sim.climate.day import ClimateDay
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services.climate_readings import probe_moments
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.crop import of_plants, scenario_crop
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.heat_log import J_PER_MJ, floor_m2
from greenhouse_sim.services.runs import RunRequest, checked_window, crop_days
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator

# The quantities each instrument gives a measure, as its definition names
# them, each in its unit: °C, %, ppm; MJ a minute; a level from 0 to 1;
# fresh g.
AIR_QUANTITIES: Final = ("temperature", "relative_humidity", "co2")
HEAT: Final = "heat"
LEVEL: Final = "level"
FRESH_MASS: Final = "fresh_mass"
# What a harvest event names its fruit by (`services.crop_log`).
HARVESTED_MASS_G: Final = "harvested_mass_g"
HARVESTED_COUNT: Final = "harvested_fruit_count"


@dataclass(frozen=True)
class HouseAirThrough:
    """The house's air at each of `times_s`, in seconds from the run's
    start, every minute and at the end: its temperature (°C), relative
    humidity (%) and CO₂ (ppm), and the heat its heaters had given it by
    then (J)."""

    times_s: tuple[float, ...]
    temperature_c: tuple[float, ...]
    relative_humidity_pct: tuple[float, ...]
    co2_ppm: tuple[float, ...]
    heated_j: tuple[float, ...]

    def samples(self, quantity: str) -> list[Sample]:
        """One quantity through time, `(moment, value)`, by its name in
        `AIR_QUANTITIES`."""
        values = {
            "temperature": self.temperature_c,
            "relative_humidity": self.relative_humidity_pct,
            "co2": self.co2_ppm,
        }[quantity]
        return list(zip(self.times_s, values, strict=True))

    def heat_mj(self) -> list[Sample]:
        """The heat given in each interval between its moments, in MJ, at
        the interval's start: summed over a window from one of its moments
        to another, the heat given over it."""
        return [
            (start, (to - since) / J_PER_MJ)
            for start, (since, to) in zip(self.times_s, pairwise(self.heated_j), strict=False)
        ]


class SetBy(StrEnum):
    """What set a device's level."""

    START = "start"  # where it stands at the run's start, no command or loop since
    LOOP = "loop"  # its controller's loop, from the house's air
    COMMAND = "command"  # a command: the run's own, every day's, or its plan's


@dataclass(frozen=True)
class DeviceState:
    """A device's level from `at_s` on, in seconds from the run's start,
    from 0 off to 1 at full, or open, and what set it."""

    at_s: float
    level: float
    set_by: SetBy


@dataclass(frozen=True)
class Picked:
    """Fruit a harvest picked from a plant, at the start of its day, `at_s`
    seconds from the run's start: how many, and their fresh mass (g)."""

    at_s: float
    plant_id: str
    fruit_count: int
    fresh_mass_g: float


def house_air(simulator: Simulator, run: RunRequest, until_s: float) -> HouseAirThrough:
    """The house's air through a run, every minute from its start to
    `until_s`, and at `until_s`. Refused as a run's climate is, and beyond
    its end."""
    config = scenario(simulator.catalogue, run.scenario_id)
    checked_window(config, 0.0, until_s)
    house = _climate(simulator, run).house
    moments = probe_moments(until_s)
    airs = [house.air_at(moment) for moment in moments]
    return HouseAirThrough(
        times_s=tuple(moments),
        temperature_c=tuple(air.temperature_c for air in airs),
        relative_humidity_pct=tuple(air.relative_humidity_pct() for air in airs),
        co2_ppm=tuple(air.co2_ppm for air in airs),
        heated_j=tuple(air.heated_j for air in airs),
    )


def heat_given(simulator: Simulator, run: RunRequest, from_s: float, until_s: float) -> float:
    """The heat a run's heaters gave its air from `from_s` to `until_s`, in
    J, as the house counts it. Refused outside the run."""
    checked_window(scenario(simulator.catalogue, run.scenario_id), from_s, until_s)
    return _climate(simulator, run).house.heated_j(from_s, until_s)


def equipment_states(
    simulator: Simulator, run: RunRequest, until_s: float
) -> dict[str, tuple[DeviceState, ...]]:
    """Each device's states from a run's start to `until_s`, by its id: its
    equipment's and its doors' and vents'. The first is its level at the
    start; each after it, a switch, of its level or of what set it, at its
    moment before `until_s`. Of two commands to a device at one moment, the
    later is the one it keeps. Refused as a run's climate is."""
    checked_window(scenario(simulator.catalogue, run.scenario_id), 0.0, until_s)
    climate = _climate(simulator, run)
    worked = climate.run
    devices = [piece.actuator_id for piece in worked.equipment]
    devices += [vent.opening_id for vent in worked.vents]
    at_start = worked.scheduled_levels_at(0.0) | worked.scheduled_openings_at(0.0)
    # Each change, by device, in the order they apply at one moment: where
    # it starts, then a command's, then a loop's, which a device a command
    # has taken over has none of.
    changes: dict[str, list[DeviceState]] = {
        device: [DeviceState(0.0, at_start[device], SetBy.START)] for device in devices
    }
    for command in worked.schedule.applied(until_s):
        if command.time_s < until_s and command.actuator_id in changes:
            changes[command.actuator_id].append(
                DeviceState(command.time_s, command.level, SetBy.COMMAND)
            )
    for moment, levels in climate.house.controlled_through(0.0, until_s):
        for device, level in levels.items():
            changes[device].append(DeviceState(moment, level, SetBy.LOOP))
    return {device: _switches(states) for device, states in changes.items()}


def _switches(changes: Sequence[DeviceState]) -> tuple[DeviceState, ...]:
    """A device's states, each a change of its level or of what set it: at
    one moment, the last change is the one it keeps."""
    ordered = sorted(changes, key=lambda state: state.at_s)
    kept: list[DeviceState] = []
    for state in ordered:
        if kept and kept[-1].at_s == state.at_s:
            kept.pop()
        if not kept or (kept[-1].level, kept[-1].set_by) != (state.level, state.set_by):
            kept.append(state)
    return tuple(kept)


def harvest(simulator: Simulator, run: RunRequest, until_s: float) -> tuple[Picked, ...]:
    """The fruit a run's crop gave from its start to `until_s`: its harvest
    events on each day that starts before then, each round's by plant as
    its event gives it, and each of its plan's harvests done, in order;
    none for a crop grown by area."""
    config = scenario(simulator.catalogue, run.scenario_id)
    checked_window(config, 0.0, until_s)
    crop = scenario_crop(simulator, run)
    if not of_plants(crop):
        return ()
    start = run_start(simulator.catalogue, run.scenario_id)
    planned = crop_days(run.plan.crop_plan())
    picked: list[Picked] = []
    for day in range(math.ceil(until_s / DAY_S)):
        at_s = day * DAY_S
        # Its records named by its scenario: only its events are read, which name no run.
        _, events = crop_records(simulator, run, day, start, run.scenario_id)
        picked += [
            Picked(
                at_s,
                event.plant_id,
                int(event.parameters[HARVESTED_COUNT]),
                float(event.parameters[HARVESTED_MASS_G]),
            )
            for event in events
            if event.event_type == EventType.HARVEST and event.plant_id is not None
        ]
        work = crop.worked_on(day) if day in planned else None
        if work is None:
            continue
        picked += [
            Picked(at_s, action.plant_id, done.effect.fruit_count, done.effect.fresh_mass_g)
            for action, done in zip(planned[day], work.done, strict=True)
            if isinstance(action, Harvest) and isinstance(done.effect, Harvested)
        ]
    return tuple(picked)


def _climate(simulator: Simulator, run: RunRequest) -> ClimateDay:
    return climate_run(simulator, run)[1]


class Instruments:
    """The evaluator's instruments on one episode's run, as carried out,
    from its start to `until_s`, the episode's end: each read the first
    time it is asked for, the equipment's states by a second pass over the
    house's air. Refused as a run's climate is, and beyond its end."""

    def __init__(self, simulator: Simulator, run: RunRequest, until_s: float) -> None:
        config = scenario(simulator.catalogue, run.scenario_id)
        checked_window(config, 0.0, until_s)
        self._simulator = simulator
        self.run = run
        self.until_s = until_s
        # What a measure per m² of floor is divided by.
        self.floor_m2 = floor_m2(config)

    @cached_property
    def house_air(self) -> HouseAirThrough:
        return house_air(self._simulator, self.run, self.until_s)

    @cached_property
    def equipment(self) -> Mapping[str, tuple[DeviceState, ...]]:
        return equipment_states(self._simulator, self.run, self.until_s)

    @cached_property
    def harvest(self) -> tuple[Picked, ...]:
        return harvest(self._simulator, self.run, self.until_s)

    def heat_given_j(self, from_s: float, until_s: float) -> float:
        """The heat given from `from_s` to `until_s` within the episode, in
        J, to the second."""
        if not 0.0 <= from_s <= until_s <= self.until_s:
            raise ValueError(
                f"the episode lasts from 0 to {self.until_s:.15g} s, "
                f"not {from_s:.15g} to {until_s:.15g}"
            )
        return heat_given(self._simulator, self.run, from_s, until_s)

    def series(self, source: FromInstrument) -> dict[str | None, list[Sample]]:
        """The series a measure's source names, as its arithmetic takes
        them (`measuring.series_value`): one, under None, or one for each
        device, for the equipment's states. A quantity its instrument does
        not give is refused."""
        quantity = source.quantity
        match source.instrument:
            case Instrument.HOUSE_AIR if quantity in AIR_QUANTITIES:
                return {None: self.house_air.samples(quantity)}
            case Instrument.HEAT_GIVEN if quantity == HEAT:
                return {None: self.house_air.heat_mj()}
            case Instrument.EQUIPMENT_STATES if quantity == LEVEL:
                return {
                    device: [(state.at_s, state.level) for state in states]
                    for device, states in self.equipment.items()
                }
            case Instrument.HARVEST if quantity == FRESH_MASS:
                return {None: [(each.at_s, each.fresh_mass_g) for each in self.harvest]}
            case instrument:
                raise ValueError(f"the {instrument} instrument gives no {quantity!r}")
