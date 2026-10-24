"""The simple daily crop as a rung of the run's crop (P14.3, decision 0035).

The simple tomato model (`greenhouse_sim.biology.tomato.simple`) grows each
plant by its daily rules, in the run as in the engine's day, by its
scenario's settings (`ScenarioConfig.simple_crop`) and from its seed:

- **A plant** is the model's plant, with the values the model keeps for it
  and for each of its fruits (`SimplePlant`), so that a plant lives its day
  alone, and a checkpoint keeps it whole.
- **Its day** is the run's: of what the run gives each plant
  (`LocalEnvironment`), it takes the day's mean air temperature, the one
  thing the model reads. Its root zone is its own, which nothing in a run
  waters: a run carries out no watering yet (P13.5).
- **The crop work:** a harvest round picks every ripe fruit; a lowering
  round lowers a plant that hangs from a wire until its top stands the
  head room under it, or by so many centimetres. Its stem is not built of
  organs, so it has no fruit, truss, leaf or internode to name: an action
  that names one is refused.
- **Its crown** rises from its foot, as tall as its stem stands.
"""

from typing import Final, Self

from greenhouse_protocol.actions import Harvest, Lower, RemoveLeaf
from greenhouse_protocol.outcome import Harvested, Lowered
from pydantic import BaseModel, ConfigDict, model_validator

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.simple.daily import advance_plant, initial_plant
from greenhouse_sim.biology.tomato.simple.state import (
    SimpleFruitState,
    SimplePlantState,
    SimpleTomatoState,
)
from greenhouse_sim.core.crop_actions import CarriedOut, CropAction
from greenhouse_sim.domain.crop import FruitStatus
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.state import PlantWorld
from greenhouse_sim.world.training import Training

CM_PER_M: Final = 100.0
# Where a simple plant's crown rises from: its foot.
AT_ITS_FOOT: Final = Vector3(x=0.0, y=0.0, z=0.0)


class SimplePlant(BaseModel):
    """A plant of the simple crop in a run: the model's plant, and the values
    the model keeps for it and for each fruit it has set, which every fruit
    on it has: its next day reads them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plant: PlantWorld
    state: SimplePlantState
    fruits: dict[str, SimpleFruitState] = {}

    @model_validator(mode="after")
    def _each_of_its_fruits_has_its_values(self) -> Self:
        missing = [
            fruit.fruit_id
            for truss in self.plant.trusses
            for fruit in truss.fruits
            if fruit.fruit_id not in self.fruits
        ]
        if missing:
            raise ValueError(f"{self.plant_id} keeps no values for its fruit {missing[0]}")
        return self

    @property
    def plant_id(self) -> str:
        return self.plant.plant_id

    def standing_cm(self) -> float:
        """How tall its stem stands: what has grown, less what is lowered."""
        return self.plant.stem_length_cm - self.plant.lowered_length_cm


class SimpleRung:
    """The simple crop as a rung of the run's crop, by `config`'s settings
    and seed: see the module."""

    def __init__(self, config: ScenarioConfig) -> None:
        self._config = config

    @property
    def plant_type(self) -> type[SimplePlant]:
        return SimplePlant

    def transplant(self, plant_id: str) -> SimplePlant:
        plant, state = initial_plant(plant_id, self._config)
        return SimplePlant(plant=plant, state=state)

    def live_day(self, plant: SimplePlant, environment: LocalEnvironment) -> SimplePlant:
        kept = SimpleTomatoState(plants={plant.plant_id: plant.state}, fruits=plant.fruits)
        lived, state, set_today = advance_plant(
            plant.plant, kept, environment.mean_temperature_c, self._config
        )
        return SimplePlant(plant=lived, state=state, fruits=plant.fruits | set_today)

    def carry_out(
        self, plant: SimplePlant, action: CropAction, training: Training | None
    ) -> CarriedOut[SimplePlant]:
        match action:
            case Harvest(organ_id=None):
                return _harvested(plant)
            case Lower(by_cm=float() as by_cm):
                return _lowered(plant, by_cm)
            case Lower(to_head_room_m=float() as head_room_m):
                if training is None or training.wire_m is None:
                    return CarriedOut(plant, refusal=f"{plant.plant_id} hangs from no wire")
                above = plant.standing_cm() - (training.wire_m - head_room_m) * CM_PER_M
                return _lowered(plant, max(0.0, above))
            case Harvest() | Lower() | RemoveLeaf():
                return CarriedOut(plant, refusal=_unnamed(plant, action))

    def crown(self, plant: SimplePlant, training: Training) -> tuple[Vector3, float]:
        return AT_ITS_FOOT, max(0.0, plant.standing_cm()) / CM_PER_M

    def recorded(self, plant: SimplePlant) -> int:
        # It keeps no history.
        return 0


def _harvested(plant: SimplePlant) -> CarriedOut[SimplePlant]:
    """Every ripe fruit picked off the plant, as the engine's harvest picks
    them (`greenhouse_sim.actions.effects`): done even when none is ripe."""
    picked = [
        fruit
        for truss in plant.plant.trusses
        for fruit in truss.fruits
        if fruit.status == FruitStatus.RIPE
    ]
    trusses = [
        truss.model_copy(
            update={
                "fruits": [
                    fruit.model_copy(update={"status": FruitStatus.HARVESTED})
                    if fruit.status == FruitStatus.RIPE
                    else fruit
                    for fruit in truss.fruits
                ]
            }
        )
        for truss in plant.plant.trusses
    ]
    mass_g = sum(fruit.mass_g for fruit in picked)
    after = plant.plant.model_copy(
        update={
            "trusses": trusses,
            "cumulative_harvest_g": plant.plant.cumulative_harvest_g + mass_g,
        }
    )
    return CarriedOut(
        plant.model_copy(update={"plant": after}),
        effect=Harvested(fruit_count=len(picked), fresh_mass_g=mass_g),
    )


def _lowered(plant: SimplePlant, by_cm: float) -> CarriedOut[SimplePlant]:
    """The plant's stem lowered by `by_cm`, as far as it stands: done even
    when that is nothing."""
    drop_cm = min(by_cm, max(0.0, plant.standing_cm()))
    after = plant.plant.model_copy(
        update={"lowered_length_cm": plant.plant.lowered_length_cm + drop_cm}
    )
    return CarriedOut(plant.model_copy(update={"plant": after}), effect=Lowered(by_cm=drop_cm))


def _unnamed(plant: SimplePlant, action: CropAction) -> str:
    """Why the simple crop does not carry out an action that names a part
    of a plant its stem is not built of."""
    match action:
        case RemoveLeaf():
            return f"{plant.plant_id} of the simple crop has no leaves"
        case Lower():
            return f"{plant.plant_id} of the simple crop has no internodes"
        case Harvest():
            return f"{plant.plant_id} of the simple crop is harvested by its ripe fruit"
