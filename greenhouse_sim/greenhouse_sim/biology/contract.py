"""What the simulator needs from a plant model.

A plant model develops a crop one day at a time. It receives the plants, the
state it keeps for itself (its `StateT`, carried between days in
`GreenhouseWorld.plant_model`) and the day's environment, which the
environment model has already advanced. It returns the plants a day later and
its updated state. How it does that, and at what fidelity, is its own
business: the simple daily rules and an organ-level model satisfy the same
contract.

A plant model must:

- return one plant per identifier from `initialize`, in the order given, and
  the same plants in the same order from `advance`;
- leave its arguments unmodified, returning new values instead;
- be deterministic: the same arguments always give the same day;
- give each plant the same day whatever other plants it is advanced with, so
  batching or splitting a crop changes nothing;
- keep state that survives a JSON round trip, so a run can be saved and
  resumed.

`greenhouse_sim/tests/test_model_contracts.py` checks every implementation
against these rules.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseEnvironment, PlantWorld


class PlantModel[StateT: BaseModel](Protocol):
    def initialize(
        self, plant_ids: Sequence[str], config: ScenarioConfig
    ) -> tuple[list[PlantWorld], StateT]:
        """New plants, one per identifier, and the model's state for them."""
        ...

    def advance(
        self,
        plants: Sequence[PlantWorld],
        state: StateT,
        environment: GreenhouseEnvironment,
        config: ScenarioConfig,
    ) -> tuple[list[PlantWorld], StateT]:
        """The plants a day later in the given environment, and the model's
        updated state."""
        ...
