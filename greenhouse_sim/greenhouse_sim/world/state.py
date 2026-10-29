"""The simple crop's plants: what is true of each, as the simple tomato
model grows it.

None of this could exist at a real greenhouse's boundary. The entities below
describe what a plant is: its size, its age, its trusses and fruit, the
water in its root zone, what has been harvested from it. Shared records hold
only what could be observed for real, and a consumer reconstructs its
picture from evidence rather than reading this one.

How a plant is grown is kept apart: the values the model invents for itself,
such as a plant's vigour or a fruit's drawn ripening day, are the model's
own (`greenhouse_sim.biology.tomato.simple.state`), and the run keeps them
beside each plant (`greenhouse_sim.core.simple_crop.SimplePlant`).
"""

from pydantic import BaseModel

from greenhouse_sim.domain.crop import FruitStatus, RipenessStage, TrussStage


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
