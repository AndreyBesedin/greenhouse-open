"""The crop's models; the simple crop model's stages: of its fruits, their
ripeness, and its trusses (`greenhouse_sim.biology.tomato.simple`); and what
a crop grown by area is driven by (`greenhouse_sim.biology.area_contract`)."""

from enum import StrEnum


class CropModel(StrEnum):
    """How a scenario's run grows its crop: plant by plant, by the simple
    daily model (`greenhouse_sim.core.simple_crop`) or organ by organ
    (`greenhouse_sim.core.crop`); or by area, by Reduced-State TOMGRO
    (`greenhouse_sim.core.tomgro_crop`, decision 0060)."""

    SIMPLE = "simple"
    ORGAN = "organ"
    REDUCED_TOMGRO = "reduced_tomgro"


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


class Driver(StrEnum):
    """A quantity a crop grown by area may be driven by, each hour's mean:
    the air's temperature or the canopy's, in °C; the PAR above the canopy,
    in µmol/m²/s; and the CO₂ in the air, in ppm."""

    AIR_TEMPERATURE = "air_temperature_c"
    CANOPY_TEMPERATURE = "canopy_temperature_c"
    PAR_ABOVE = "par_above_umol_m2_s"
    CO2 = "co2_ppm"
