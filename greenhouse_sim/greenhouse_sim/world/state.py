"""The simulator's hidden state: what is true of the simulated world.

None of this could exist at a real greenhouse's boundary. The entities below
describe what the world is: sizes, ages, stages, the water in each plant's
root zone, what has been harvested. `simulated_day` is the simulator's own
clock. Shared records hold only what could be observed for real, and a
consumer reconstructs its picture from evidence rather than reading this one.

How the world is generated is kept apart. `GreenhouseWorld.plant_model` holds
the values the plant model invents for itself, such as a plant's vigour or a
fruit's drawn ripening day. It belongs to that model: it travels with the
world so a run can be saved and resumed, and nothing else reads it.

What leaves the simulator on the normal path is `SimulationStep.observations`;
this is what those observations are noisy measurements *of*.
"""

from enum import StrEnum

from pydantic import BaseModel

from greenhouse_sim.biology.tomato.simple.state import SimpleTomatoState


class FruitStatus(StrEnum):
    GROWING = "GROWING"
    RIPE = "RIPE"
    HARVESTED = "HARVESTED"


class RipenessStage(StrEnum):
    FRUIT_SET = "FRUIT_SET"
    IMMATURE_GREEN = "IMMATURE_GREEN"
    MATURE_GREEN = "MATURE_GREEN"
    TURNING = "TURNING"
    RIPE = "RIPE"
    OVERRIPE = "OVERRIPE"


class TrussStage(StrEnum):
    INITIATED = "INITIATED"
    FRUITING = "FRUITING"
    HARVESTABLE = "HARVESTABLE"
    INACTIVE = "INACTIVE"


class Fruit(BaseModel):
    fruit_id: str
    truss_id: str
    plant_id: str
    age_days: int = 0
    diameter_mm: float = 0.0
    mass_g: float = 0.0
    ripeness_stage: RipenessStage = RipenessStage.FRUIT_SET
    status: FruitStatus = FruitStatus.GROWING


class Truss(BaseModel):
    truss_id: str
    plant_id: str
    index: int
    age_days: int = 0
    stage: TrussStage = TrussStage.INITIATED
    fruits: list[Fruit] = []


class PlantWorld(BaseModel):
    plant_id: str
    age_days: int = 0
    stem_length_cm: float
    lowered_length_cm: float = 0.0
    water_reservoir_ml: float
    trusses: list[Truss] = []
    cumulative_harvest_g: float = 0.0


class GreenhouseEnvironment(BaseModel):
    air_temperature_c: float
    humidity_pct: float


class GreenhouseWorld(BaseModel):
    greenhouse_id: str
    simulated_day: int
    environment: GreenhouseEnvironment
    plants: list[PlantWorld]
    plant_model: SimpleTomatoState

    def plant(self, plant_id: str) -> PlantWorld:
        for plant in self.plants:
            if plant.plant_id == plant_id:
                return plant
        raise LookupError(f"no plant {plant_id!r} in greenhouse world {self.greenhouse_id!r}")
