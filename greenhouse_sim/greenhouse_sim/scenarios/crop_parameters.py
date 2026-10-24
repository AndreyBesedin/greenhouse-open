"""The parameters of a scenario's crop and of its crop walk, each in a
section of its own (P14.3, decision 0054).

A scenario's configuration holds each crop model's parameters under its
`crop`, told apart by their `kind`, the model's name, as it holds the
weather's and the air field's; and the walk's measurement noises under its
`crop_walk`. A manifest gives them in its `models`
(`greenhouse_sim.scenarios.registry`).
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, NonNegativeInt, PositiveFloat, PositiveInt

# The crop walk's one model.
WALK: Final = "walk"


class SimpleCrop(BaseModel):
    """The simple daily crop's settings (`greenhouse_sim.biology.tomato.simple`),
    and those of the engine's day it grows in: the bounds its air drifts
    within (`greenhouse_sim.environment.simple`) and its sensors' noises
    (`greenhouse_sim.sensors.generation`), until the engine goes (decision
    0035)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["simple"] = "simple"

    # Environment: bounds the smooth day-to-day drift stays within.
    air_temperature_bounds: tuple[float, float] = (18.0, 32.0)
    humidity_bounds: tuple[float, float] = (45.0, 85.0)

    # Water reservoir / stress.
    initial_water_reservoir_ml: float = 600.0
    water_capacity_ml: PositiveFloat = 1200.0
    water_use_ml_per_day_base: float = 80.0
    evaporation_ml_per_day: float = 20.0
    water_stress_threshold_pct: float = 35.0

    # Stem / truss growth.
    initial_stem_length_cm: float = 20.0
    stem_growth_cm_per_day_base: float = 2.0
    truss_interval_days: PositiveInt = 6
    max_trusses: NonNegativeInt = 8
    fruits_per_truss_bounds: tuple[int, int] = (3, 6)

    # Fruit growth / ripening.
    target_diameter_mm_bounds: tuple[float, float] = (18.0, 26.0)
    fruit_growth_days_to_target: PositiveInt = 20
    mass_coefficient_g_per_mm3: float = 0.0012
    ripening_days_bounds: tuple[int, int] = (16, 26)

    # The engine's sensors' noises (standard deviations).
    soil_moisture_noise_pct: float = 3.0
    air_temperature_noise_c: float = 0.4


class OrganCrop(BaseModel):
    """The organ crop's settings (`greenhouse_sim.biology.tomato.organ`):
    none a scenario chooses yet, its variety's being its own (P12.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["organ"] = "organ"


class CropWalk(BaseModel):
    """The daily walk through the crop's measurement errors, on either
    crop's walk (`greenhouse_sim.services.crop_log`, and the engine's
    sensors): the chance that a count is one off, and the standard
    deviations of the ripe fruits' estimated mass, in percent, and of a
    plant's measured height, in cm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["walk"] = WALK

    fruit_count_noise_probability: float = 0.1
    ripe_mass_noise_pct: float = 8.0
    height_noise_cm: float = 1.5


# The simple crop's settings when a scenario's crop is of another model: those
# the engine's day grows the simple crop by in its place.
DEFAULT_SIMPLE_CROP: Final = SimpleCrop()

# The settings a scenario's configuration held at its top until P14.3, and a
# manifest until format 5, by the section that holds them now: the simple
# crop's, with those of the engine's day it grows in, and the crop walk's.
HELD_AT_THE_TOP: Final = {
    "crop": (
        "air_temperature_bounds",
        "humidity_bounds",
        "initial_water_reservoir_ml",
        "water_capacity_ml",
        "water_use_ml_per_day_base",
        "evaporation_ml_per_day",
        "water_stress_threshold_pct",
        "initial_stem_length_cm",
        "stem_growth_cm_per_day_base",
        "truss_interval_days",
        "max_trusses",
        "fruits_per_truss_bounds",
        "target_diameter_mm_bounds",
        "fruit_growth_days_to_target",
        "mass_coefficient_g_per_mm3",
        "ripening_days_bounds",
        "soil_moisture_noise_pct",
        "air_temperature_noise_c",
    ),
    "crop_walk": ("fruit_count_noise_probability", "ripe_mass_noise_pct", "height_noise_cm"),
}
