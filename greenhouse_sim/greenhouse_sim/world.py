"""The simulator's hidden state: what is true of the simulated world.

None of this could exist at a real greenhouse's boundary.
`growth_multiplier`, `ripening_day`, `target_diameter_mm` and `water_stress`
are latent variables the simulator invents in order to generate a world, and
`simulated_day` is the simulator's own clock. Shared records hold only what
could be observed for real, and a consumer reconstructs its picture from
evidence rather than reading this one.

What leaves the simulator on the normal path is `SimulationStep.observations`;
this is what those observations are noisy measurements *of*.
"""

from enum import StrEnum

from pydantic import BaseModel


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
    target_diameter_mm: float
    growth_rate_multiplier: float
    ripening_day: int


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
    water_stress: float = 0.0
    growth_multiplier: float = 1.0
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

    def plant(self, plant_id: str) -> PlantWorld:
        for plant in self.plants:
            if plant.plant_id == plant_id:
                return plant
        raise LookupError(f"no plant {plant_id!r} in greenhouse world {self.greenhouse_id!r}")
