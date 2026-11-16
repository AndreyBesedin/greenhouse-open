"""The parameters of a scenario's crop and of its crop walk, each in a
section of its own (P14.3, decision 0054).

A scenario's configuration holds each crop model's parameters under its
`crop`, told apart by their `kind`, the model's name, as it holds the
weather's and the air field's; and what measures the crop under its
`crop_walk`, the part of the registry that holds the crop's measurement
models (decision 0062): the walk among its plants, or a sample of a canopy
grown by area. A manifest gives them in its `models`
(`greenhouse_sim.scenarios.registry`).
"""

from typing import Annotated, Any, ClassVar, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

# The crop walk's one model.
WALK: Final = "walk"
CANOPY_SAMPLE: Final = "canopy_sample"
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

    # Whether the model grows the crop by area, with no plants (decision
    # 0062), so that it takes no crop work and its canopy stands under the
    # eaves.
    BY_AREA: ClassVar[bool] = False

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
    none a scenario chooses yet, its variety's being its own (P20)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    BY_AREA: ClassVar[bool] = False

    kind: Literal["organ"] = "organ"


# What a parameter set is called: lower-case letters, digits and underscores.
SET_NAME: Final = r"^[a-z0-9][a-z0-9_]*$"
# The version a section names when it names none, its published set's.
FIRST_SET_VERSION: Final = 1


class CarriedSet(BaseModel):
    """A parameter set other than its model's published one, as the
    simulator that registered its scenario resolved it
    (`greenhouse_sim.services.parameter_sets`, decision 0077): the files of
    the set and of each of its bases that is not published, its own first;
    every value it resolves to, by its model's parameters' fields; and its
    digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    files: tuple[dict[str, JsonValue], ...]
    values: dict[str, float]
    digest: str


def _first_version(version: int) -> bool:
    """Whether a section names its set's first version, which it leaves
    unwritten, so that a run under a published set is named as it was."""
    return version == FIRST_SET_VERSION


class ReducedTomgroCrop(BaseModel):
    """Reduced-State TOMGRO's settings, grown by area
    (`greenhouse_sim.biology.tomato.tomgro`, decisions 0060 and 0062): the
    parameter set it runs, gnvman unless it names another, the driver
    profile, named and versioned, through which the run gives it its drivers
    (`greenhouse_sim.core.drivers`), and the height above its planting
    positions at which the light above its canopy is read, which the model
    does not grow: the run's choice, in m, not the model's."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    BY_AREA: ClassVar[bool] = True
    PUBLISHED_SET: ClassVar[str] = "gnvman"

    kind: Literal["reduced_tomgro"] = "reduced_tomgro"

    parameter_set: str = Field(default=PUBLISHED_SET, pattern=SET_NAME)
    parameter_set_version: PositiveInt = Field(default=FIRST_SET_VERSION, exclude_if=_first_version)
    driver_profile: Literal["house_hours"] = "house_hours"
    driver_profile_version: Literal[1] = 1
    canopy_height_m: PositiveFloat = 2.0
    carried: Annotated[SkipJsonSchema[CarriedSet | None], Field(exclude=True, repr=False)] = None


class VanthoorKatzinCrop(BaseModel):
    """The settings of Vanthoor's model as Katzin simplified it, grown by
    area (`greenhouse_sim.biology.tomato.vanthoor`, decisions 0060 and
    0062): the parameter set it runs, GreenLight 2.0.7's unless it names
    another, the driver profile, named and versioned, through which the run
    gives it its drivers (`greenhouse_sim.core.drivers`), and the height
    above its planting positions at which the light above its canopy is
    read, which the model does not grow: the run's choice, in m, not the
    model's."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    BY_AREA: ClassVar[bool] = True
    PUBLISHED_SET: ClassVar[str] = "greenlight_2_0_7"

    kind: Literal["vanthoor_katzin"] = "vanthoor_katzin"

    parameter_set: str = Field(default=PUBLISHED_SET, pattern=SET_NAME)
    parameter_set_version: PositiveInt = Field(default=FIRST_SET_VERSION, exclude_if=_first_version)
    driver_profile: Literal["house_hours"] = "house_hours"
    driver_profile_version: Literal[1] = 1
    canopy_height_m: PositiveFloat = 2.0
    carried: Annotated[SkipJsonSchema[CarriedSet | None], Field(exclude=True, repr=False)] = None


# A crop section grown by area names the parameter set it runs by name and
# version, as it names its driver profile (decision 0077): its published set
# (`PUBLISHED_SET`) unless it says otherwise. A set other than that one is
# looked up among those its simulator keeps when its scenario is registered,
# and carried, resolved, by the section (`carried`), as a recorded weather
# carries its file; its written form names it.
type WithASet = ReducedTomgroCrop | VanthoorKatzinCrop


def runs_published(section: WithASet) -> bool:
    """Whether a section runs its model's published set."""
    return (section.parameter_set, section.parameter_set_version) == (
        section.PUBLISHED_SET,
        FIRST_SET_VERSION,
    )


def carried_set(section: WithASet) -> CarriedSet | None:
    """The set a section carries: none for its model's published set.
    Refused for a set it names and does not carry, rather than run with
    another's."""
    if runs_published(section):
        return None
    carried = section.carried
    if carried is None:
        raise ValueError(
            f"the parameter set {section.parameter_set} v{section.parameter_set_version} of "
            f"{section.kind} is not carried: a scenario is registered with the set it runs"
        )
    return carried


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


class CanopySample(BaseModel):
    """A sample taken of each scope of a crop grown by area, a measurement
    model (decision 0062): every `every_days` days from the run's first, at
    the walk's moment, each quantity read with a relative error, in percent,
    of a normal spread `noise_pct` about the bias `bias_pct`. Its defaults
    are an exploratory choice, not a source's. Noise and bias at zero make
    it a perfect instrument, for research, which a manifest has to ask for.
    It takes nothing from the canopy, as the air takes nothing from it, and
    its readings are delivered as they are taken."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["canopy_sample"] = CANOPY_SAMPLE

    every_days: PositiveInt = 7
    noise_pct: NonNegativeFloat = 5.0
    bias_pct: float = Field(default=0.0, gt=-100.0)


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
