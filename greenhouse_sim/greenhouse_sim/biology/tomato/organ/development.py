"""How a plant develops, organ by organ, as thermal time accumulates.

Thermal time is the plant's clock: each day adds its mean temperature above
a base, counting nothing below it and nothing past a cap, in degree-days
(°Cd). A plant emerges with one phytomer, and a new one appears at the top
of the stem every phyllochron. Each internode and leaf appears at a small
share of its final size, fixed when it appears, and grows to all of it along
a smooth S-curve of its thermal age, over the organs' expansion time: a leaf
is expanding until then, and mature after. Final sizes grow up the stem, from
the first phytomer's, a share of the full sizes, to the full sizes themselves
from a set rank up.

Development depends on thermal time alone here, so a plant grown in one step
or day by day is the same plant. Trusses, flowers and fruits are carried as
they are, until P03.5 grows them.
"""

from collections.abc import Iterable
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt

from greenhouse_sim.biology.tomato.organ.topology import (
    Axis,
    Internode,
    Leaf,
    LeafStage,
    Phytomer,
    Plant,
    internode_id,
    leaf_id,
    phytomer_id,
    stem_id,
)

type Fraction = Annotated[float, Field(gt=0, lt=1)]

# The smoothstep curve, 3p² - 2p³: flat at both ends, steepest halfway.
SMOOTHSTEP_SQUARE: Final = 3
SMOOTHSTEP_CUBE: Final = 2


class DevelopmentParams(BaseModel):
    """The rates and sizes a plant develops by, with a tomato's typical
    values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # A day's mean temperature counts from this base, up to this cap, in °C.
    base_temperature_c: float = 10.0
    cap_temperature_c: float = 30.0
    # Thermal time between one phytomer's appearance and the next's, in °Cd.
    phyllochron_cd: PositiveFloat = 33.0
    # How long an internode or leaf grows after it appears, in °Cd.
    expansion_cd: PositiveFloat = 160.0
    # An organ appears at this share of its final length, and an internode at
    # this share of its final diameter.
    initial_fraction: Fraction = 0.1
    initial_diameter_fraction: Fraction = 0.5
    # The full final sizes, which phytomers from `full_size_rank` up reach;
    # the first phytomer's are `first_phytomer_fraction` of them.
    internode_length_cm: PositiveFloat = 7.0
    internode_diameter_mm: PositiveFloat = 11.0
    leaf_length_cm: PositiveFloat = 45.0
    first_phytomer_fraction: Fraction = 0.35
    full_size_rank: PositiveInt = 10


def daily_thermal_time(mean_temperature_c: float, params: DevelopmentParams) -> float:
    """The thermal time a day of this mean temperature adds, in °Cd."""
    capped = min(mean_temperature_c, params.cap_temperature_c)
    return max(0.0, capped - params.base_temperature_c)


def growth_fraction(age_cd: float, initial: float, params: DevelopmentParams) -> float:
    """The share of its final size an organ of this thermal age has reached:
    `initial` when it appears, rising along a smooth S-curve to all of it
    when its expansion time has passed."""
    progress = min(1.0, max(0.0, age_cd / params.expansion_cd))
    smooth = progress * progress * (SMOOTHSTEP_SQUARE - SMOOTHSTEP_CUBE * progress)
    return min(1.0, initial + (1 - initial) * smooth)


def final_size_fraction(rank: int, params: DevelopmentParams) -> float:
    """The share of the full final sizes a phytomer of this rank grows to."""
    if params.full_size_rank == 1:
        return 1.0
    ramp = min(1.0, (rank - 1) / (params.full_size_rank - 1))
    return params.first_phytomer_fraction + (1 - params.first_phytomer_fraction) * ramp


def _new_phytomer(plant_id: str, rank: int, born_tt: float, params: DevelopmentParams) -> Phytomer:
    """A phytomer as it appears, its organs at their initial sizes."""
    scale = final_size_fraction(rank, params)
    internode_length = params.internode_length_cm * scale
    internode_diameter = params.internode_diameter_mm * scale
    leaf_length = params.leaf_length_cm * scale
    return Phytomer(
        phytomer_id=phytomer_id(plant_id, rank),
        rank=rank,
        born_tt=born_tt,
        internode=Internode(
            internode_id=internode_id(plant_id, rank),
            born_tt=born_tt,
            length_cm=internode_length * params.initial_fraction,
            diameter_mm=internode_diameter * params.initial_diameter_fraction,
            final_length_cm=internode_length,
            final_diameter_mm=internode_diameter,
        ),
        leaf=Leaf(
            leaf_id=leaf_id(plant_id, rank),
            born_tt=born_tt,
            length_cm=leaf_length * params.initial_fraction,
            final_length_cm=leaf_length,
        ),
    )


def _grown(phytomer: Phytomer, thermal_time: float, params: DevelopmentParams) -> Phytomer:
    """The phytomer's internode and leaf at the plant's thermal time. A leaf
    that has been removed stays removed."""
    age = thermal_time - phytomer.born_tt
    length = growth_fraction(age, params.initial_fraction, params)
    diameter = growth_fraction(age, params.initial_diameter_fraction, params)
    internode = phytomer.internode
    leaf = phytomer.leaf
    if leaf.stage != LeafStage.REMOVED:
        leaf = leaf.model_copy(
            update={
                "length_cm": leaf.final_length_cm * length,
                "stage": LeafStage.MATURE if age >= params.expansion_cd else LeafStage.EXPANDING,
            }
        )
    return phytomer.model_copy(
        update={
            "internode": internode.model_copy(
                update={
                    "length_cm": internode.final_length_cm * length,
                    "diameter_mm": internode.final_diameter_mm * diameter,
                }
            ),
            "leaf": leaf,
        }
    )


def emerged(plant_id: str, params: DevelopmentParams) -> Plant:
    """A plant as it emerges: no thermal time yet, and its first phytomer."""
    return Plant(
        plant_id=plant_id,
        born_tt=0.0,
        thermal_time=0.0,
        stem=Axis(
            axis_id=stem_id(plant_id),
            born_tt=0.0,
            phytomers=(_new_phytomer(plant_id, 1, 0.0, params),),
        ),
    )


def develop(plant: Plant, thermal_time_cd: float, params: DevelopmentParams) -> Plant:
    """The plant after this much more thermal time: its organs grown, and a
    phytomer for every phyllochron that has passed since the youngest
    appeared, each appearing when its phyllochron is up."""
    thermal_time = plant.thermal_time + thermal_time_cd
    phytomers = list(plant.stem.phytomers)
    born = phytomers[-1].born_tt + params.phyllochron_cd if phytomers else plant.born_tt
    while born <= thermal_time:
        phytomers.append(_new_phytomer(plant.plant_id, len(phytomers) + 1, born, params))
        born += params.phyllochron_cd
    grown = tuple(_grown(phytomer, thermal_time, params) for phytomer in phytomers)
    return plant.model_copy(
        update={
            "thermal_time": thermal_time,
            "stem": plant.stem.model_copy(update={"phytomers": grown}),
        }
    )


def grow(
    plant: Plant, daily_mean_temperatures_c: Iterable[float], params: DevelopmentParams
) -> Plant:
    """The plant after these days, one after another, at these mean
    temperatures."""
    for temperature in daily_mean_temperatures_c:
        plant = develop(plant, daily_thermal_time(temperature, params), params)
    return plant
