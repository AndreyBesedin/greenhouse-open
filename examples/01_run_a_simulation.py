"""Play a scenario's run and look at what its sensors and its crop walk deliver.

    python examples/01_run_a_simulation.py

A run's truth, the house's air where each sensor stands and each plant as
its model grows it, is not what the simulator publishes. It publishes only
noisy observations of it, as a real greenhouse's sensors and the people
walking its crop would: each sensor with the imperfections its layout gives
it (noise, bias, drift, readings dropped or delivered late), and each plant
measured with the walk's errors. A consumer reads those through the consumer
interface, as it reads any producer's (decision 0040), and nothing else of
the run.

Here the climate box's run is played back (decision 0041), its clock moved by
hand a day at a time, and each day's observations are read once the clock
has passed it. The same scenario and seed played again deliver the same
records.
"""

import tempfile
import textwrap
import time
from pathlib import Path
from typing import Final

from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import consumer, playback
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "climate_box"  # a small, shut house of 32 plants
DAYS: Final = 3
# Two temperature sensors in the same small, shut house, and the first plant
# of the walk.
SENSORS: Final = ("temperature_front", "temperature_back")
PLANT: Final = "climate_box_plant_001"
# The run plays a simulated day in a day of its clock, which the example
# moves by hand, a day at a time.
SECONDS_PER_DAY: Final = DAY_S
WAIT_S: Final = 0.05


class Clock:
    """The seconds a playback reads its moment from, moved by the example."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def advance(played: Playback, clock: Clock, time_s: float) -> None:
    """Moves the run to `time_s` into it. A playback's moment follows its
    clock no further than its records are worked out, and drops the rest of
    a clock's jump: so the clock moves once they reach `time_s`, and again
    from wherever the run stopped short."""
    while (state := played.state()).time_s < time_s:
        if state.worked_out_s < time_s:
            time.sleep(WAIT_S)
            continue
        clock.now += (time_s - state.time_s) / DAY_S * SECONDS_PER_DAY


def run(days: int) -> list[list[Observation]]:
    """Each day's observations of a fresh run of the scenario, as a consumer
    reads them: what was delivered by the day's end, after what it read the
    day before. Its epochs are kept in a folder of its own, gone after."""
    with tempfile.TemporaryDirectory() as kept, Simulator() as simulator:
        clock = Clock()
        run_id = playback.start(
            simulator,
            SCENARIO,
            SECONDS_PER_DAY,
            hold=True,
            clock=clock,
            epochs=Epochs(Path(kept)),
        ).run_id
        played = playback.playback(simulator, SCENARIO)
        played.command(PlaybackCommand.PLAY)
        seen: int | None = None
        per_day: list[list[Observation]] = []
        for day in range(1, days + 1):
            advance(played, clock, day * DAY_S)
            observations: list[Observation] = []
            while True:
                delivered = consumer.observations(simulator, run_id, after=seen)
                observations += delivered.observations
                seen = delivered.next
                if not delivered.has_more:
                    break
            per_day.append(observations)
        return per_day


def read(observations: list[Observation], sensor_id: str) -> str:
    """The lowest and highest a sensor read, in °C."""
    values = [o.value for o in observations if o.sensor_id == sensor_id]
    return f"{min(values):.1f} to {max(values):.1f} °C" if values else "no reading"


def main() -> None:
    per_day = run(DAYS)
    print(f"day  observations  {SENSORS[0]:>18}  {SENSORS[1]:>18}  {PLANT}")
    for day, observations in enumerate(per_day, start=1):
        height = next(
            o.value
            for o in observations
            if o.plant_id == PLANT and o.observation_type is ObservationType.VISIBLE_HEIGHT_CM
        )
        print(
            f"{day:3}  {len(observations):12}  {read(observations, SENSORS[0]):>18}  "
            f"{read(observations, SENSORS[1]):>18}  measured {height:.1f} cm tall"
        )
    delivered = [o for observations in per_day for o in observations]
    sensors = {o.sensor_id for o in delivered if o.sensor_id is not None}
    plants = {o.plant_id for o in delivered if o.plant_id is not None}
    kinds = sorted({o.observation_type.value for o in delivered})
    print(
        f"{len(sensors)} sensors, a daily walk through {len(plants)} plants and the heat "
        f"given each hour: {len(kinds)} kinds of observation"
    )
    print(textwrap.fill(", ".join(kinds), initial_indent="  ", subsequent_indent="  "))

    # Same scenario, same seed: a second run delivers identical records.
    assert run(DAYS) == per_day
    print("a second run delivered identical observations")


if __name__ == "__main__":
    main()
