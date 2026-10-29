"""The parameters of a scenario's crop and of its crop walk, each in a
section of its own (P14.3, decision 0054).

A scenario's configuration holds each crop model's parameters under its
`crop`, told apart by their `kind`, the model's name, as it holds the
weather's and the air field's; and the walk's measurement noises under its
`crop_walk`. A manifest gives them in its `models`
(`greenhouse_sim.scenarios.registry`).
"""

from typing import Any, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

# The crop walk's one model.
WALK: Final = "walk"
# The settings of the engine's day the simple crop grew in until it was
# removed (decision 0059): the bounds its air drifted within, and its
# sensors' noises. No run read them. A manifest, a checkpoint or a stored
# configuration written before may still hold them, so they are dropped
# where read rather than refused.
RETIRED: Final = (
    "air_temperature_bounds",
    "humidity_bounds",
    "soil_moisture_noise_pct",
    "air_temperature_noise_c",
)


class SimpleCrop(BaseModel):
    """The simple daily crop's settings
    (`greenhouse_sim.biology.tomato.simple`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["simple"] = "simple"

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

    @model_validator(mode="before")
    @classmethod
    def _without_the_engines_settings(cls, given: Any) -> Any:
        """Settings written with the engine's day's (`RETIRED`), as they
        were before it was removed, read without them."""
        if not isinstance(given, dict):
            return given
        return {name: value for name, value in given.items() if name not in RETIRED}


class OrganCrop(BaseModel):
    """The organ crop's settings (`greenhouse_sim.biology.tomato.organ`):
    none a scenario chooses yet, its variety's being its own (P12.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["organ"] = "organ"


class ReducedTomgroCrop(BaseModel):
    """Reduced-State TOMGRO's settings, grown by area
    (`greenhouse_sim.biology.tomato.tomgro`, decisions 0060 and 0062): the
    published parameter set it runs, the driver profile, named and
    versioned, through which the run gives it its drivers
    (`greenhouse_sim.core.drivers`), and the height above its planting
    positions at which the light above its canopy is read, which the model
    does not grow: the run's choice, in m, not the model's."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["reduced_tomgro"] = "reduced_tomgro"

    parameter_set: Literal["gnvman"] = "gnvman"
    driver_profile: Literal["house_hours"] = "house_hours"
    driver_profile_version: Literal[1] = 1
    canopy_height_m: PositiveFloat = 2.0


class CropWalk(BaseModel):
    """The daily walk through the crop's measurement errors, on either
    crop's walk (`greenhouse_sim.services.crop_log`): the chance that a
    count is one off, and the standard deviations of the ripe fruits'
    estimated mass, in percent, and of a plant's measured height, in cm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["walk"] = WALK

    fruit_count_noise_probability: float = 0.1
    ripe_mass_noise_pct: float = 8.0
    height_noise_cm: float = 1.5


# The simple crop's settings when a scenario's crop is of another model: its
# own defaults.
DEFAULT_SIMPLE_CROP: Final = SimpleCrop()

# The settings a scenario's configuration held at its top until P14.3, and a
# manifest until format 5, by the section that holds them now: the simple
# crop's, with those of the engine's day it grew in (`RETIRED`), and the crop
# walk's.
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
