"""The tomato's values for what fruiting crops' organ-level models share
(`greenhouse_sim.biology.plant`): how its growth responds to light and CO₂,
and how its plants vary. Its own development, trusses, fruit and form carry
theirs as their parameters' defaults.
"""

from typing import Final

from greenhouse_sim.biology.plant.environment import ResponseParams
from greenhouse_sim.biology.plant.variation import TraitSpread, VariationParams

# A tomato makes all of its potential growth from 25 mol/m²/d of PAR and
# 800 ppm of CO₂, and half its saturated response at 10 mol/m²/d and 300 ppm.
TOMATO_RESPONSES: Final = ResponseParams(
    reference_par_mol_m2_day=25.0,
    reference_co2_ppm=800.0,
    par_half_saturation_mol_m2_day=10.0,
    co2_half_saturation_ppm=300.0,
)

# A tomato crop's typical spreads: vigorous plants develop faster and grow
# longer internodes, thicker stems and longer leaves; how a plant holds its
# leaves varies mostly on its own.
TOMATO_VARIATION: Final = VariationParams(
    phyllochron=TraitSpread(cv=0.06, vigour_loading=-0.6),
    internode_length=TraitSpread(cv=0.12, vigour_loading=0.6),
    stem_diameter=TraitSpread(cv=0.1, vigour_loading=0.8),
    leaf_length=TraitSpread(cv=0.1, vigour_loading=0.8),
    leaf_insertion=TraitSpread(cv=0.12),
    leaf_droop=TraitSpread(cv=0.15, vigour_loading=-0.3),
)
