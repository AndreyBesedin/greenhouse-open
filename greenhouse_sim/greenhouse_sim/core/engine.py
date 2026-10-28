"""Stepping a simulated greenhouse forward. No database, no server.

This is the simulator's own API: create a world, advance it, collect
observations. Persisting any of it, deciding what to do with the
observations, and running a management policy are the caller's business. A
policy acts on the run, through its gateway (P13.9), not on this day.

Two deliberate omissions:

- Ground truth does not leave here through the normal path. `advance`
  returns the hidden world alongside the observations because the caller
  owns checkpointing it, but everything a consumer uses to decide should be
  derived from `SimulationStep.observations`. Evaluation is the explicit
  exception (`greenhouse_sim.ground_truth`).
- The environment, plant and sensor models are injected, each defaulting
  to the simple implementation, so a different fidelity
  level or a specialized physics backend plugs in without changing this
  interface. What each model must do is stated in its domain's
  `contract.py`.
"""

from datetime import datetime

from greenhouse_protocol.observation import Observation
from pydantic import BaseModel

from greenhouse_sim.biology.contract import PlantModel
from greenhouse_sim.biology.tomato.simple.model import SimpleTomatoModel
from greenhouse_sim.environment.contract import EnvironmentModel
from greenhouse_sim.environment.simple import SimpleEnvironmentModel
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.sensors.contract import SensorModel
from greenhouse_sim.sensors.generation import SimpleSensorModel
from greenhouse_sim.world.state import GreenhouseWorld, PlantModelState
from greenhouse_sim.world_builder import advance_world, initialize_world


class SimulationStep(BaseModel):
    """One advanced day: the new hidden world, and what a sensor saw of it."""

    day: int
    timestamp: datetime
    world: GreenhouseWorld
    observations: list[Observation]


class SimulationEngine:
    def __init__(
        self,
        config: ScenarioConfig,
        *,
        environment_model: EnvironmentModel | None = None,
        plant_model: PlantModel[PlantModelState] | None = None,
        sensor_model: SensorModel | None = None,
    ) -> None:
        """`plant_model` is limited to models whose state the world can carry
        (`PlantModelState`)."""
        self._config = config
        self._environment_model = environment_model or SimpleEnvironmentModel()
        self._plant_model = plant_model or SimpleTomatoModel()
        self._sensor_model = sensor_model or SimpleSensorModel()

    @property
    def config(self) -> ScenarioConfig:
        return self._config

    def initialize(self, plant_ids: list[str], *, greenhouse_id: str) -> GreenhouseWorld:
        return initialize_world(
            self._config,
            plant_ids,
            greenhouse_id=greenhouse_id,
            environment_model=self._environment_model,
            plant_model=self._plant_model,
        )

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
        advanced = advance_world(
            world,
            self._config,
            day,
            environment_model=self._environment_model,
            plant_model=self._plant_model,
        )
        observations = self._sensor_model.observe(
            advanced, self._config, day=day, timestamp=timestamp, simulation_id=simulation_id
        )
        return SimulationStep(
            day=day, timestamp=timestamp, world=advanced, observations=observations
        )
