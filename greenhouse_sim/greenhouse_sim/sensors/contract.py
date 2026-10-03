"""What the simulator needs from a sensor model.

A sensor model reports what instruments would read from the hidden world: its
observations are what leaves the simulator on the normal path. It sees the
world's entities, never a model's own state (`GreenhouseWorld.plant_model`).

A sensor model must:

- produce observations that pass the canonical contract's conformance checks;
- stamp every observation with the given instant and simulation, scope it to
  the world's greenhouse, and name either no plant or a plant in the world;
- leave the world unmodified and be deterministic: the same world, scenario,
  day and instant always give the same observations.

`greenhouse_sim/tests/test_model_contracts.py` checks every implementation
against these rules.
"""

from datetime import datetime
from typing import Protocol

from greenhouse_protocol.observation import Observation

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseWorld


class SensorModel(Protocol):
    def observe(
        self,
        world: GreenhouseWorld,
        config: ScenarioConfig,
        *,
        day: int,
        timestamp: datetime,
        simulation_id: str,
    ) -> list[Observation]:
        """What the sensors report about the world at `timestamp`."""
        ...
