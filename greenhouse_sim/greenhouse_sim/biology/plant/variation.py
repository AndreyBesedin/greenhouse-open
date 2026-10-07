"""How plants of one crop differ: correlated, seeded variation.

Each plant draws a latent vigour, then a factor for each of its traits, from
the seed hierarchy (`seeds`). A trait's factor is 1 plus its coefficient of
variation times a standard normal draw, which loads on the plant's vigour as
the trait's correlation with it says, and on the trait's own draw for the
rest. Every draw is held within a set number of standard deviations, so
every factor stays within its configured range, and each plant is also
turned about its stem by a uniform draw. How much each trait varies, and how
it follows vigour, is each crop's own (for the tomato,
`greenhouse_sim.biology.tomato.organ.parameters`).

A plant's draws depend only on the seed and the plant's identifier, never on
which other plants exist.
"""

import math
from typing import Annotated, Final, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator

from greenhouse_sim.biology.plant.organs import PlantTraits
from greenhouse_sim.biology.plant.seeds import plant_rng

FULL_TURN_RAD: Final = 2 * math.pi


class TraitSpread(BaseModel):
    """How much one trait varies among plants, and how it follows vigour."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The factor's coefficient of variation.
    cv: Annotated[float, Field(ge=0)]
    # Its correlation with the plant's vigour, from -1 to 1.
    vigour_loading: Annotated[float, Field(ge=-1, le=1)] = 0.0


class VariationParams(BaseModel):
    """How the plants of a crop vary: each trait's spread."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phyllochron: TraitSpread
    internode_length: TraitSpread
    stem_diameter: TraitSpread
    leaf_length: TraitSpread
    leaf_insertion: TraitSpread
    leaf_droop: TraitSpread
    # Every draw is held within this many standard deviations of its mean.
    limit_sd: PositiveFloat = 2.5

    @model_validator(mode="after")
    def _factors_stay_positive(self) -> Self:
        for name, spread in self.spreads().items():
            if spread.cv * self.limit_sd >= 1:
                raise ValueError(f"{name} could vary to nothing: lower its cv or limit_sd")
        return self

    def spreads(self) -> dict[str, TraitSpread]:
        """Each varying trait's spread, by the name of its factor in
        `PlantTraits` without its `_scale`."""
        return {
            "phyllochron": self.phyllochron,
            "internode_length": self.internode_length,
            "stem_diameter": self.stem_diameter,
            "leaf_length": self.leaf_length,
            "leaf_insertion": self.leaf_insertion,
            "leaf_droop": self.leaf_droop,
        }

    def factor_range(self, spread: TraitSpread) -> tuple[float, float]:
        """The lowest and highest factor a trait of this spread can take."""
        reach = spread.cv * self.limit_sd
        return 1 - reach, 1 + reach


def _held(draw: float, limit: float) -> float:
    return min(limit, max(-limit, draw))


def draw_traits(seed: int, plant_id: str, variation: VariationParams) -> PlantTraits:
    """A plant's traits, drawn from its own generators."""
    limit = variation.limit_sd
    vigour = _held(float(plant_rng(seed, plant_id, "vigour").standard_normal()), limit)
    factors = {}
    for name, spread in variation.spreads().items():
        own = float(plant_rng(seed, plant_id, name).standard_normal())
        loading = spread.vigour_loading
        draw = loading * vigour + math.sqrt(1 - loading * loading) * own
        factors[f"{name}_scale"] = 1 + spread.cv * _held(draw, limit)
    rotation = float(plant_rng(seed, plant_id, "rotation").uniform(0, FULL_TURN_RAD))
    return PlantTraits.model_validate(
        {"vigour": vigour, "rotation_rad": rotation % FULL_TURN_RAD, **factors}
    )
