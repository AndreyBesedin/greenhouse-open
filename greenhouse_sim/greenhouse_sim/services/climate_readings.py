"""What a run's climate reads at its moments: probes in its air, the
house's air as one volume, its equipment, its glazing and its openings.

Each is asked for as the run's climate field is
(`greenhouse_sim.services.fields`), and refused as it is.

Probes read the grid run that draws the moment asked for, every minute from
its start, beside the same run with everything off
(`greenhouse_sim.climate.probes`). The house's air as one well-mixed volume
(`greenhouse_sim.climate.house`) is read every minute from the run's
start.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.climate.day import window_start
from greenhouse_sim.climate.glazing import GlazingAt
from greenhouse_sim.climate.house import HouseAir, HouseTrace, house_trace
from greenhouse_sim.climate.openings import OpeningsAt
from greenhouse_sim.climate.probes import ClimateProbes, probe_series
from greenhouse_sim.services.climate_runs import RunKey, climate_day, everything_off
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.fields import climate_key, grid
from greenhouse_sim.services.runs import RunRequest, checked_moment, checked_window
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.world.geometry import Vector3

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# Probes read a climate run this often, in seconds.
PROBE_EVERY_S: Final = 60.0


def _climate_of(simulator: Simulator, run: RunRequest) -> RunKey:
    """What names a run's climate, refused for a scenario without
    equipment, which has no climate run."""
    key = climate_key(simulator, run)
    if key is None:
        raise NotFound(f"scenario {run.scenario_id!r} has no climate: it has no equipment")
    return key


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
    key = _climate_of(simulator, run)
    air = grid(simulator.catalogue, scenario_id)
    probed = [Vector3(x=x, y=y, z=z) for x, y, z in points]
    outside = [point for point in probed if not air.contains(point)]
    if outside:
        named = ", ".join(f"({p.x:g}, {p.y:g}, {p.z:g})" for p in outside)
        raise InvalidRequest(f"a probe stands in the house's air, not at {named}")
    return probe_series(
        climate_day(simulator, key).window(until_s),
        everything_off(simulator, key).window(until_s),
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
    key = _climate_of(simulator, run)
    return house_trace(
        climate_day(simulator, key).house,
        everything_off(simulator, key).house,
        _moments(until_s, first),
    )


def house_air_at(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> HouseAir | None:
    """The house's air as one well-mixed volume at a moment of a run's
    climate, asked as its climate field is and refused as it is; None for a
    scenario without equipment, which has no climate run. Unlike
    `house_air`, it works out nothing of the same run all off."""
    checked_moment(scenario(simulator.catalogue, run.scenario_id), time_s)
    key = climate_key(simulator, run)
    if key is None:
        return None
    return climate_day(simulator, key).house.air_at(time_s)


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
    key = climate_key(simulator, run)
    if key is None:
        return EquipmentAt(time_s=time_s, levels={}, thermostat=None)
    worked = climate_day(simulator, key).run
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
    key = _climate_of(simulator, run)
    return climate_day(simulator, key).glazing_at(time_s)


def openings(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> OpeningsAt:
    """What a run's open doors and vents pass at `time_s` into its climate,
    as the wind and the stack drive them (`greenhouse_sim.climate.openings`).
    Asked as its climate field is, and refused as it is."""
    scenario_id = run.scenario_id
    checked_moment(scenario(simulator.catalogue, scenario_id), time_s)
    key = _climate_of(simulator, run)
    return climate_day(simulator, key).openings_at(time_s)
