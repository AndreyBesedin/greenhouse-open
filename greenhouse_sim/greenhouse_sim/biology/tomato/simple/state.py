"""What the simple tomato model keeps for itself about each plant and fruit.

These values are how the model generates a world, not part of what the world
is: a plant's vigour and water stress, and each fruit's drawn target size,
growth rate and ripening day. No sensor measures them, and nothing outside
the model reads them. The world carries them in `GreenhouseWorld.plant_model`
only so that a run can be saved and resumed.
"""

from typing import Literal

from pydantic import BaseModel


class SimplePlantState(BaseModel):
    growth_multiplier: float
    water_stress: float = 0.0


class SimpleFruitState(BaseModel):
    target_diameter_mm: float
    growth_rate_multiplier: float
    ripening_day: int


class SimpleTomatoState(BaseModel):
    """The model's values for every plant and fruit, keyed by identifier."""

    model: Literal["tomato.simple"] = "tomato.simple"
    plants: dict[str, SimplePlantState] = {}
    fruits: dict[str, SimpleFruitState] = {}
