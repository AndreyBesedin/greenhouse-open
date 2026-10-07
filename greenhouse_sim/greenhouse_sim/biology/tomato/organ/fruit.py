"""How a fruit grows and ripens, from set to red.

When a flower sets, its fruit draws two things from its own generator: the
diameter it will grow to, around the crop's, and smaller the further along
its truss it sits; and its ripening offset, how much earlier or later than a
typical fruit it starts to ripen. It grows from the diameter it set at to
its final one along a smooth S-curve over its growth time. It starts to
ripen, at breaker, a set thermal age after it set, scaled by its offset, and
ripens from green to red over its ripening time: its ripeness runs from 0 to
1 and never goes back. Each step, a fruit makes the growth its curve gives,
times the step's growth factor (`environment`). Its fresh mass follows from its volume, and its
maturity class, from green through breaker, turning, pink and light red to
red, from its ripeness.

A fruit that has aborted or been harvested grows and ripens no more.
"""

import math
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat

from greenhouse_sim.biology.plant.curves import smoothstep
from greenhouse_sim.biology.plant.organs import Fruit
from greenhouse_sim.biology.plant.seeds import organ_rng
from greenhouse_sim.biology.tomato.organ.topology import Plant

MM_PER_CM: Final = 10
# A sphere's volume is this fraction of its diameter cubed: π/6.
SPHERE_VOLUME_FRACTION: Final = math.pi / 6


class Maturity(StrEnum):
    """A fruit's ripeness class, as a grader names it."""

    GREEN = "green"
    BREAKER = "breaker"
    TURNING = "turning"
    PINK = "pink"
    LIGHT_RED = "light_red"
    RED = "red"


# The least ripeness of each class above green, ripest first.
MATURITY_FROM: Final = (
    (0.85, Maturity.RED),
    (0.6, Maturity.LIGHT_RED),
    (0.4, Maturity.PINK),
    (0.2, Maturity.TURNING),
)

type Fraction = Annotated[float, Field(ge=0, lt=1)]


class FruitParams(BaseModel):
    """How fruits grow and ripen, with a truss tomato's typical values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # A fruit's diameter when it sets, and a typical first fruit's final one,
    # in millimetres.
    set_diameter_mm: PositiveFloat = 6.0
    final_diameter_mm: PositiveFloat = 62.0
    # Fruits vary around that by this coefficient of variation, and each
    # flower further along its truss bears a fruit this share smaller.
    final_diameter_cv: Fraction = 0.08
    distal_size_decline: Fraction = 0.04
    # How long a fruit grows after it sets, and how long a typical fruit
    # takes from set to breaker and from breaker to red, in °Cd.
    growth_cd: PositiveFloat = 450.0
    breaker_cd: PositiveFloat = 480.0
    ripening_cd: PositiveFloat = 100.0
    # How much a fruit's time to breaker varies, as a coefficient of
    # variation of its factor.
    ripening_offset_cv: Fraction = 0.08
    # Draws are held within this many standard deviations.
    limit_sd: Annotated[float, Field(gt=0, le=3)] = 2.5
    # Fresh fruit's density, in grams per cubic centimetre.
    density_g_per_cm3: PositiveFloat = 1.0


def maturity(ripeness: float) -> Maturity:
    """The class of a fruit this ripe: green until it starts to ripen."""
    for least, named in MATURITY_FROM:
        if ripeness >= least:
            return named
    return Maturity.BREAKER if ripeness > 0 else Maturity.GREEN


def fruit_mass_g(diameter_mm: float, params: FruitParams) -> float:
    """A fruit's fresh mass, from the volume of a sphere of its diameter."""
    diameter_cm = diameter_mm / MM_PER_CM
    return params.density_g_per_cm3 * SPHERE_VOLUME_FRACTION * diameter_cm**3


def _factor(plant: Plant, organ_id: str, process: str, cv: float, params: FruitParams) -> float:
    draw = float(organ_rng(plant.seed, plant.plant_id, organ_id, process).standard_normal())
    return 1 + cv * min(params.limit_sd, max(-params.limit_sd, draw))


def set_fruit(
    plant: Plant, fruit_id: str, flower_rank: int, born_tt: float, params: FruitParams
) -> Fruit:
    """The fruit a flower in this place on its truss sets at this thermal
    time: at its set diameter, its final diameter and its ripening offset
    drawn from its own generator."""
    typical = params.final_diameter_mm * (1 - params.distal_size_decline * (flower_rank - 1))
    final = max(
        params.set_diameter_mm,
        typical * _factor(plant, fruit_id, "size", params.final_diameter_cv, params),
    )
    offset = _factor(plant, fruit_id, "ripening", params.ripening_offset_cv, params)
    return Fruit(
        fruit_id=fruit_id,
        born_tt=born_tt,
        diameter_mm=params.set_diameter_mm,
        final_diameter_mm=final,
        mass_g=fruit_mass_g(params.set_diameter_mm, params),
        breaker_tt=born_tt + params.breaker_cd * offset,
    )


def grown_fruit(
    fruit: Fruit,
    previous_tt: float,
    thermal_time: float,
    params: FruitParams,
    growth: float = 1.0,
) -> Fruit:
    """The fruit grown and ripened as the plant's thermal time moves on from
    `previous_tt`, making `growth` of its potential growth (all of it unless
    said)."""
    before = smoothstep((max(previous_tt, fruit.born_tt) - fruit.born_tt) / params.growth_cd)
    after = smoothstep((thermal_time - fruit.born_tt) / params.growth_cd)
    gain = (fruit.final_diameter_mm - params.set_diameter_mm) * (after - before) * growth
    diameter = min(fruit.final_diameter_mm, fruit.diameter_mm + gain)
    ripeness = min(1.0, max(0.0, (thermal_time - fruit.breaker_tt) / params.ripening_cd))
    return fruit.model_copy(
        update={
            "diameter_mm": diameter,
            "mass_g": fruit_mass_g(diameter, params),
            "ripeness": max(fruit.ripeness, ripeness),
        }
    )
