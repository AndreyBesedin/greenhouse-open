"""Stepping a simulated greenhouse forward. No database, no server.

This is the simulator's own API: create a world, advance it, apply actions,
collect observations. Persisting any of it, deciding what to do with the
observations, and running a management policy are the caller's business.

Two deliberate omissions:

- Ground truth does not leave here through the normal path. `advance`
  returns the hidden world alongside the observations because the caller
  owns checkpointing it, but everything a consumer uses to decide should be
  derived from `SimulationStep.observations`. Evaluation is the explicit
  exception (`greenhouse_sim.ground_truth`).
- The dynamics are reached through `world_builder`, and the executor is
  injected, so a different fidelity level or a specialized physics backend
  can be plugged in later without changing this interface.
"""

from datetime import datetime

from greenhouse_protocol.action import ActionResult, RequestedAction
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel

from greenhouse_sim.executor import ActionExecutor, SimulatedOperatorExecutor
from greenhouse_sim.observations import generate_observations
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.validation import validate_action
from greenhouse_sim.world import GreenhouseWorld
from greenhouse_sim.world_builder import advance_world, initialize_world


class SimulationStep(BaseModel):
    """One advanced day: the new hidden world, and what a sensor saw of it."""

    day: int
    timestamp: datetime
    world: GreenhouseWorld
    observations: list[Observation]


class ActionExecution(BaseModel):
    """The outcome of offering actions to the world.

    `results` is positional with the actions given, so a rejected request
    keeps its place. `events` covers only the accepted ones - a request is
    not evidence that anything happened.
    """

    world: GreenhouseWorld
    results: list[ActionResult]
    events: list[Event]


class SimulationEngine:
    def __init__(self, config: ScenarioConfig, *, executor: ActionExecutor | None = None) -> None:
        self._config = config
        self._executor = executor or SimulatedOperatorExecutor()

    @property
    def config(self) -> ScenarioConfig:
        return self._config

    def initialize(self, plant_ids: list[str], *, greenhouse_id: str) -> GreenhouseWorld:
        return initialize_world(self._config, plant_ids, greenhouse_id=greenhouse_id)

    def advance(
        self,
        world: GreenhouseWorld,
        *,
        day: int,
        timestamp: datetime,
        simulation_id: str,
    ) -> SimulationStep:
        """Evolves the world by one day and observes the result.

        Deterministic for a given world, config and day: the same inputs
        produce the same step, which is what makes a run reproducible
        (greenhouse_sim/tests/test_run_characterization.py).
        """
        advanced = advance_world(world, self._config, day)
        generation = generate_observations(
            advanced, self._config, day=day, timestamp=timestamp, simulation_id=simulation_id
        )
        return SimulationStep(
            day=day,
            timestamp=timestamp,
            world=advanced,
            observations=generation.observations,
        )

    def apply_actions(
        self,
        world: GreenhouseWorld,
        actions: list[RequestedAction],
        *,
        day: int,
        timestamp: datetime,
    ) -> ActionExecution:
        """Validates each action against the world and executes the accepted ones.

        Every action is checked here, however it was proposed or approved.
        Actions are applied in order against one in-memory
        world, so a caller approving several at once pays for one world
        round-trip rather than one per action.
        """
        results: list[ActionResult] = []
        events: list[Event] = []
        for action in actions:
            result = validate_action(world, action)
            results.append(result)
            if not result.accepted:
                continue
            world, event = self._executor.apply(
                world, action, self._config, day=day, timestamp=timestamp
            )
            events.append(event)
        return ActionExecution(world=world, results=results, events=events)
