"""What each process of a scenario's run holds at a moment (P09.6), for QA
mode's developer panel: the clock, the house's air, the crop's days, the
equipment's levels and the latest commands it was given, each sensor's
freshness and each camera's latest frame.

Each part is what its own service gives at the moment (`services.fields`,
`services.sensors`), read through its contract, not from another process's
internals. The run is asked for as its climate field is, and refused as it
is. None of it is the sensors' truth, which leaves by its own path.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.climate.commands import Command
from greenhouse_sim.core.clock import days_ended, run_day
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.sensors.log import SensorFreshness
from greenhouse_sim.services.fields import equipment_at, house_air_at, run_schedule
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import SceneChanges, changed, plant_ids, scenario
from greenhouse_sim.services.sensors import CameraAt, sensors_at

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# How many of the latest commands a run's state lists.
LATEST_COMMANDS: Final = 5


class HouseAirNow(BaseModel):
    """The house's air as one well-mixed volume at a moment."""

    model_config = ConfigDict(frozen=True)

    temperature_c: float
    humidity_pct: float
    co2_ppm: float


class RunState(BaseModel):
    """What each process of a run holds at a moment."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    # The clock: when the run started, the moment, in seconds from its
    # start, its day, and the instant it is.
    start: datetime
    time_s: float
    day: int
    at: datetime
    # The house's air, if the run has a climate: none without equipment.
    house_air: HouseAirNow | None
    # The crop: how it grows, how many plants, and how many of the run's
    # days they have lived by then, the days that have ended.
    crop_model: str
    plants: int
    days_lived: int
    # The equipment and the doors and vents: each one's level, how far it
    # stands open, by identifier; how many commands the run has given,
    # from its start, and the latest of them, the last last.
    levels: dict[str, float]
    commands_given: int
    latest_commands: list[Command]
    # The sensors, each one's freshness, and the cameras, each one's frames.
    sensors: list[SensorFreshness]
    cameras: list[CameraAt]


def run_state(simulator: Simulator, run: RunRequest, until_s: float = 0.0) -> RunState:
    """What each process of a run holds at `until_s`, the run asked for as
    its climate field is: with one of its scenario's layouts, its equipment
    at its levels from the start, then as its daily commands and its
    commands set it, its doors and vents open as it asks, under a
    weather."""
    found = sensors_at(simulator, run, until_s=until_s)
    air = house_air_at(simulator, run, time_s=until_s)
    config = changed(
        scenario(run.scenario_id),
        SceneChanges(layout=run.layout or DEFAULT_LAYOUT, openings=dict(run.openings)),
    )
    given = run_schedule(run).applied(until_s)
    # Every piece of equipment starts off, every door and vent as open as it
    # stands, until a command sets it.
    now = {piece.actuator_id: 0.0 for piece in config.layout.equipment} | {
        opening.opening_id: opening.opening for opening in config.envelope.openings
    }
    for command in given:
        now[command.actuator_id] = command.level
    # A thermostat runs its heater by the air, not by commands.
    now |= equipment_at(simulator, run, time_s=until_s).levels
    return RunState(
        run_id=found.run_id,
        start=found.start,
        time_s=until_s,
        day=run_day(until_s),
        at=found.start + timedelta(seconds=until_s),
        house_air=None
        if air is None
        else HouseAirNow(
            temperature_c=air.temperature_c,
            humidity_pct=air.relative_humidity_pct(),
            co2_ppm=air.co2_ppm,
        ),
        crop_model=config.crop_model.value,
        plants=len(plant_ids(config)),
        days_lived=days_ended(until_s),
        levels=now,
        commands_given=len(given),
        latest_commands=given[-LATEST_COMMANDS:],
        sensors=found.freshness,
        cameras=found.cameras,
    )
