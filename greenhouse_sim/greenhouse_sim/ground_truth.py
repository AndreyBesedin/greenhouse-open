"""What is actually true of the simulated world, for evaluation only.

The simulator knows a plant's real height and exactly how many of its
fruits are ripe. Its sensors report those quantities with noise, and a
consumer reconstructs its picture from the noisy readings, as it would have
to in a real greenhouse. That gap is the whole value of simulation for
evaluation: it is the only setting where a prediction can be scored against
what was really the case.

Truth leaves the simulator by a separate path from observations:

    simulator -- sensor observations --> canonical records --> consumer
        |
        +-- ground truth -------------> evaluation only

So this is a separate interface, not a richer observation. Decision-making
code must never read it, or a policy would be scored on a shortcut that
disappears the moment it meets a real greenhouse. Within this package only
`greenhouse_sim.evaluation` imports it, and a test enforces that.

The quantities here are deliberately the ones the simulator's sensors
report, so an evaluation can compare a reading against the truth it was
derived from. Latent variables that no sensor targets, like a plant's
growth multiplier, stay inside the world model.
"""

from datetime import datetime

from pydantic import BaseModel

from greenhouse_sim.world import FruitStatus, GreenhouseWorld, PlantWorld


class PlantTruth(BaseModel):
    """What a perfect sensor would report for one plant."""

    plant_id: str
    soil_moisture_pct: float
    visible_fruit_count: int
    ripe_fruit_count: int
    ripe_mass_g: float
    visible_height_cm: float
    cumulative_harvest_g: float


class GroundTruth(BaseModel):
    greenhouse_id: str
    timestamp: datetime
    air_temperature_c: float
    plants: list[PlantTruth]

    def plant(self, plant_id: str) -> PlantTruth:
        for plant in self.plants:
            if plant.plant_id == plant_id:
                return plant
        raise LookupError(f"no plant {plant_id!r} in this ground truth")


def ground_truth(
    world: GreenhouseWorld, *, timestamp: datetime, water_capacity_ml: float
) -> GroundTruth:
    """The noiseless reading of every quantity the simulator's sensors report.

    `water_capacity_ml` comes from the scenario, because soil moisture is a
    percentage of it - the same conversion `greenhouse_sim.observations` makes
    before adding noise.
    """
    return GroundTruth(
        greenhouse_id=world.greenhouse_id,
        timestamp=timestamp,
        air_temperature_c=world.environment.air_temperature_c,
        plants=[_plant_truth(plant, water_capacity_ml) for plant in world.plants],
    )


def _plant_truth(plant: PlantWorld, water_capacity_ml: float) -> PlantTruth:
    fruits = [fruit for truss in plant.trusses for fruit in truss.fruits]
    visible = [fruit for fruit in fruits if fruit.status != FruitStatus.HARVESTED]
    ripe = [fruit for fruit in visible if fruit.status == FruitStatus.RIPE]

    return PlantTruth(
        plant_id=plant.plant_id,
        soil_moisture_pct=100.0 * plant.water_reservoir_ml / water_capacity_ml,
        visible_fruit_count=len(visible),
        ripe_fruit_count=len(ripe),
        ripe_mass_g=sum(fruit.mass_g for fruit in ripe),
        visible_height_cm=plant.stem_length_cm - plant.lowered_length_cm,
        cumulative_harvest_g=plant.cumulative_harvest_g,
    )
