"""Store a run's observations and query them through the canonical contracts.

    python examples/02_store_and_query.py

A consumer never needs to know which producer wrote a record. It stores
observations through `ObservationStore`, reads them back through
`ObservationQuery`, and asks for them only up to the instant it is deciding
at, so it cannot see the future. The in-memory store here is the reference
implementation; a database-backed one satisfies the same contracts.

The records are those a consumer reads of the climate box's run, played back
with its clock moved by hand a day at a time (decision 0041), as example 01
reads them: each day's checked against the contract and stored as it comes.
"""

import tempfile
import time
from datetime import timedelta
from pathlib import Path
from typing import Final

from greenhouse_protocol.contracts.canonical_store import ObservationQuery, ObservationStore
from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.contracts.memory import InMemoryObservations
from greenhouse_protocol.observation import Observation
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import consumer, playback
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "climate_box"  # a small, shut house of 32 plants
DAYS: Final = 3
# The instant the consumer decides at, in hours into the run: noon of its
# second day.
DECIDED_AFTER_H: Final = 36
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


def main() -> None:
    records = InMemoryObservations()
    store: ObservationStore = records
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
        described = consumer.run(simulator, run_id)
        plant_id = consumer.greenhouse(simulator, run_id).plants[0].plant_id
        seen: int | None = None
        for day in range(1, DAYS + 1):
            advance(played, clock, day * DAY_S)
            observations: list[Observation] = []
            while True:
                delivered = consumer.observations(simulator, run_id, after=seen)
                observations += delivered.observations
                seen = delivered.next
                if not delivered.has_more:
                    break
            # A consumer can check what it is given against the contract,
            # as a producer can check its own output.
            violations = check_observations(observations)
            assert not violations, violations
            store.save_many(observations)
            print(f"day {day}: {len(observations)} observations delivered, checked and stored")

    greenhouse_id = described.greenhouse_id
    query: ObservationQuery = records
    everything = query.list_for_greenhouse(greenhouse_id)
    decided_at = described.started_at + timedelta(hours=DECIDED_AFTER_H)
    known_then = query.list_for_greenhouse(greenhouse_id, up_to=decided_at)
    one_plant = query.list_for_greenhouse(greenhouse_id, plant_id=plant_id)

    print(f"stored {len(everything)} observations of {greenhouse_id} over {DAYS} days")
    print(
        f"known at {decided_at:%Y-%m-%d %H:%M %Z}, {DECIDED_AFTER_H} h into the run: "
        f"{len(known_then)}, none taken later"
    )
    print(f"for {plant_id}: {len(one_plant)}, from the daily walk")
    assert all(o.timestamp <= decided_at for o in known_then)
    assert len(known_then) < len(everything)


if __name__ == "__main__":
    main()
