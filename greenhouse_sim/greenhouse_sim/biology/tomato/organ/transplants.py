"""A tomato crop's transplants: the plants the plant lab and a scenario's
organ-level crop (P09.3) start from.

Each plant is a transplant of one crop: its traits drawn from a seed, as the
crop's plants vary (`parameters`), its organs varying around its own sizes,
and already `TRANSPLANT_CD` into its development when its first day starts.
The same seed and plant always give the same transplant.
"""

from typing import Final

from greenhouse_sim.biology.plant.variation import draw_traits
from greenhouse_sim.biology.tomato.organ.development import DevelopmentParams, develop, emerged
from greenhouse_sim.biology.tomato.organ.parameters import TOMATO_VARIATION
from greenhouse_sim.biology.tomato.organ.topology import Plant

# How far into their development the transplants are on their first day.
TRANSPLANT_CD: Final = 230.0
# The crop: how its plants develop, their organs varying around each plant's
# sizes, and how its plants vary.
DEVELOPMENT: Final = DevelopmentParams(organ_size_cv=0.08)
VARIATION: Final = TOMATO_VARIATION


def transplant(plant_id: str, seed: int) -> Plant:
    """The crop's plant `plant_id` on its first day, drawn from `seed`."""
    traits = draw_traits(seed, plant_id, VARIATION)
    return develop(emerged(plant_id, DEVELOPMENT, seed, traits), TRANSPLANT_CD, DEVELOPMENT)
