"""What the simulator needs from an environment model.

An environment model produces the climate the crop lives in, one day at a
time, before the plant model responds to it. It must leave its arguments
unmodified and be deterministic: the same environment, scenario and day
always give the same next environment.

The simple model keeps no state beyond the environment it returns. A model
that does, such as a spatial field, will need the contract to carry its state
the way `PlantModel` does.

`greenhouse_sim/tests/test_model_contracts.py` checks every implementation
against these rules.
"""

from typing import Protocol

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseEnvironment


class EnvironmentModel(Protocol):
    def initial(self, config: ScenarioConfig) -> GreenhouseEnvironment:
        """The environment before the first day."""
        ...

    def advance(
        self, environment: GreenhouseEnvironment, config: ScenarioConfig, day: int
    ) -> GreenhouseEnvironment:
        """The environment of `day`, given the day before's."""
        ...
