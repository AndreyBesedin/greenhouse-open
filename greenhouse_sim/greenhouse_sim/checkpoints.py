"""Where a simulated world is kept between steps.

`SimulationEngine` is pure: it takes a world and returns the next one, and
some caller has to hold onto that world. Simulator persistence captures
enough hidden state to reproduce a world; operational storage captures what
a real system could observe. They are different concerns even when they
share a database. This protocol is the simulator's side of that line:
anything that can hold a world can back a run, and `InMemoryWorldCheckpoints`
is enough to run the simulator standalone, with no database at all.

Checkpoints are keyed by the simulator's own clock, which is correct here
and would not be in an operational table: `simulated_day` is a step count
in a synthetic world, not an instant in a greenhouse's chronology.
"""

from typing import Protocol

from greenhouse_sim.world import GreenhouseWorld


class WorldCheckpoints(Protocol):
    """Somewhere to keep a run's hidden state between steps."""

    def save(self, world: GreenhouseWorld) -> None: ...

    def get_latest(self, greenhouse_id: str) -> GreenhouseWorld | None: ...

    def delete_for_greenhouse(self, greenhouse_id: str) -> None: ...


class InMemoryWorldCheckpoints:
    """The default: enough to run a simulation in a process, and nothing more.

    Keeps one world per greenhouse, the latest saved. A store that needs to
    rewind, branch or reproduce a past run keeps every step instead; that is
    a simulator concern too, left open until something needs it.
    """

    def __init__(self) -> None:
        self._worlds: dict[str, GreenhouseWorld] = {}

    def save(self, world: GreenhouseWorld) -> None:
        self._worlds[world.greenhouse_id] = world

    def get_latest(self, greenhouse_id: str) -> GreenhouseWorld | None:
        return self._worlds.get(greenhouse_id)

    def delete_for_greenhouse(self, greenhouse_id: str) -> None:
        self._worlds.pop(greenhouse_id, None)
