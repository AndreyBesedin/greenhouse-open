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

A plant develops by its crop's parameters as its traits change them
(`plant_params`): its own phyllochron and full sizes. Each organ's final size
also varies around its plant's, drawn from the organ's own generator when it
appears, so one plant's leaves are not all alike.

Trusses appear with their phytomers and develop their flowers and fruits as
`reproduction` says.

Development depends on thermal time alone here, so a plant grown in one step
or day by day is the same plant.
"""

from collections.abc import Iterable
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt

from greenhouse_sim.biology.tomato.organ.reproduction import (
    TrussParams,
    bears_truss,
    grown_truss,
    new_truss,
)
from greenhouse_sim.biology.tomato.organ.seeds import organ_rng
from greenhouse_sim.biology.tomato.organ.topology import (
    Axis,
    Internode,
    Leaf,
    LeafStage,
    Phytomer,
    Plant,
    PlantTraits,
    Truss,
    internode_id,
    leaf_id,
    phytomer_id,
    stem_id,
)

type Fraction = Annotated[float, Field(gt=0, lt=1)]

# The smoothstep curve, 3p² - 2p³: flat at both ends, steepest halfway.
SMOOTHSTEP_SQUARE: Final = 3
SMOOTHSTEP_CUBE: Final = 2
# An organ's own variation is held within this many standard deviations.
ORGAN_LIMIT_SD: Final = 2.5


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
    # Each organ's final size varies around its plant's by this coefficient
    # of variation; none unless asked.
    organ_size_cv: Annotated[float, Field(ge=0, lt=1 / ORGAN_LIMIT_SD)] = 0.0
    # When trusses appear and how their flowers develop.
    trusses: TrussParams = TrussParams()


def plant_params(params: DevelopmentParams, traits: PlantTraits) -> DevelopmentParams:
    """The crop's parameters as a plant of these traits develops by them."""
    return params.model_copy(
        update={
            "phyllochron_cd": params.phyllochron_cd * traits.phyllochron_scale,
            "internode_length_cm": params.internode_length_cm * traits.internode_length_scale,
            "internode_diameter_mm": params.internode_diameter_mm * traits.stem_diameter_scale,
            "leaf_length_cm": params.leaf_length_cm * traits.leaf_length_scale,
        }
    )


def organ_factor(plant: Plant, organ_id: str, process: str, params: DevelopmentParams) -> float:
    """How far an organ's final size departs from its plant's, as a factor:
    drawn from the organ's own generator, or 1 if organs do not vary."""
    if params.organ_size_cv == 0:
        return 1.0
    draw = float(organ_rng(plant.seed, plant.plant_id, organ_id, process).standard_normal())
    return 1 + params.organ_size_cv * min(ORGAN_LIMIT_SD, max(-ORGAN_LIMIT_SD, draw))


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


def _new_phytomer(
    plant: Plant, rank: int, born_tt: float, params: DevelopmentParams, truss: Truss | None
) -> Phytomer:
    """A phytomer as it appears on the plant, which develops by `params`, its
    organs at their initial sizes, with this truss if it bears one."""
    plant_id = plant.plant_id
    internode, leaf = internode_id(plant_id, rank), leaf_id(plant_id, rank)
    scale = final_size_fraction(rank, params)
    internode_length = (
        params.internode_length_cm * scale * organ_factor(plant, internode, "length", params)
    )
    internode_diameter = (
        params.internode_diameter_mm * scale * organ_factor(plant, internode, "diameter", params)
    )
    leaf_length = params.leaf_length_cm * scale * organ_factor(plant, leaf, "length", params)
    return Phytomer(
        phytomer_id=phytomer_id(plant_id, rank),
        rank=rank,
        born_tt=born_tt,
        internode=Internode(
            internode_id=internode,
            born_tt=born_tt,
            length_cm=internode_length * params.initial_fraction,
            diameter_mm=internode_diameter * params.initial_diameter_fraction,
            final_length_cm=internode_length,
            final_diameter_mm=internode_diameter,
        ),
        leaf=Leaf(
            leaf_id=leaf,
            born_tt=born_tt,
            length_cm=leaf_length * params.initial_fraction,
            final_length_cm=leaf_length,
        ),
        truss=truss,
    )


def _grown(
    plant: Plant,
    phytomer: Phytomer,
    previous_tt: float,
    thermal_time: float,
    params: DevelopmentParams,
) -> Phytomer:
    """The phytomer's internode, leaf and truss as the plant's thermal time
    moves on from `previous_tt`. A leaf that has been removed stays removed."""
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
            "truss": None
            if phytomer.truss is None
            else grown_truss(plant, phytomer.truss, previous_tt, thermal_time, params.trusses),
        }
    )


def emerged(
    plant_id: str,
    params: DevelopmentParams,
    seed: int = 0,
    traits: PlantTraits | None = None,
) -> Plant:
    """A plant as it emerges, with these traits (by default a typical
    plant's) and drawing from this seed: no thermal time yet, and its first
    phytomer."""
    bare = Plant(
        plant_id=plant_id,
        born_tt=0.0,
        thermal_time=0.0,
        stem=Axis(axis_id=stem_id(plant_id), born_tt=0.0),
        seed=seed,
        traits=PlantTraits() if traits is None else traits,
    )
    own = plant_params(params, bare.traits)
    truss = new_truss(bare, 1, 0.0, own.trusses) if bears_truss(1, own.trusses) else None
    first = _new_phytomer(bare, 1, 0.0, own, truss)
    return bare.model_copy(update={"stem": bare.stem.model_copy(update={"phytomers": (first,)})})


def develop(plant: Plant, thermal_time_cd: float, params: DevelopmentParams) -> Plant:
    """The plant after this much more thermal time, developing by its crop's
    `params` as its traits change them: its organs grown, and a phytomer for
    every phyllochron that has passed since the youngest appeared, each
    appearing when its phyllochron is up."""
    own = plant_params(params, plant.traits)
    thermal_time = plant.thermal_time + thermal_time_cd
    phytomers = list(plant.stem.phytomers)
    trusses = sum(phytomer.truss is not None for phytomer in phytomers)
    born = phytomers[-1].born_tt + own.phyllochron_cd if phytomers else plant.born_tt
    while born <= thermal_time:
        rank = len(phytomers) + 1
        truss = None
        if bears_truss(rank, own.trusses):
            trusses += 1
            truss = new_truss(plant, trusses, born, own.trusses)
        phytomers.append(_new_phytomer(plant, rank, born, own, truss))
        born += own.phyllochron_cd
    grown = tuple(
        _grown(plant, phytomer, plant.thermal_time, thermal_time, own) for phytomer in phytomers
    )
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
