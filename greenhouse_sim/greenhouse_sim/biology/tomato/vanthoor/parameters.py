"""Vanthoor's model's parameters and its state (decision 0060).

The parameters and the initial state are GreenLight 2.0.7's, as the
reproduction's manifest records each with its unit and source
(`research/reproductions/vanthoor_katzin/manifest.json`). "Table" is that of
Vanthoor's thesis. Each field is named by the published symbol.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveFloat

from greenhouse_sim.biology.parameter_fields import parameter

# Where most parameters' values come from, as the reproduction's manifest
# says each.
TABLE_9_1: Final = "Vanthoor (2011), Table 9.1"
TABLE_9_2: Final = "Vanthoor (2011), Table 9.2"
EXTENSION: Final = "as the standalone extension gives it"
# Why each range's most is what it is.
CURVE: Final = (
    "a curvature, of the non-rectangular hyperbola: above 1 the electron transport is not"
    " a real number where light and its most are alike (growth.py)"
)
STOMATA: Final = "a share of the air's CO₂, which the stomata take theirs from: all of it at most"
REFLECTED: Final = (
    "a share of the PAR that reaches it, all of it at most: above 1 the canopy absorbs less"
    " than none (growth.py)"
)


class VanthoorParameters(BaseModel):
    """The model's parameters, as GreenLight's crop definition and its
    standalone extension give them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lai_max: PositiveFloat = parameter(
        3.0,
        what="laiMax: the most leaf area",
        unit="m² leaf m⁻² floor",
        source="Vanthoor (2011), Table 2.2, the Netherlands",
    )
    alpha: PositiveFloat = parameter(
        0.385,
        what="alpha: the electrons from the photons the canopy absorbs",
        unit="µmol e⁻ µmol⁻¹ photons",
        source=TABLE_9_1,
    )
    theta: PositiveFloat = parameter(
        0.7,
        what="θ: the curvature of the electron transport's response to light",
        unit="-",
        source=TABLE_9_1,
        most=1.0,
        most_from=CURVE,
    )
    eta_co2_air_stom: PositiveFloat = parameter(
        0.67,
        what="ηCO2,AirStom: the stomata's CO₂ as a share of the air's",
        unit="-",
        source=TABLE_9_1,
        most=1.0,
        most_from=STOMATA,
    )
    c_gamma: NonNegativeFloat = parameter(
        1.7,
        what="cΓ: the temperature's effect on the CO₂ compensation point Γ",
        unit="µmol mol⁻¹ K⁻¹",
        source=TABLE_9_1,
    )
    c_fruit_m: NonNegativeFloat = parameter(
        1.16e-7,
        what="cFruit,m: the fruit's maintenance respiration",
        unit="mg mg⁻¹ s⁻¹",
        source=TABLE_9_1,
    )
    c_leaf_m: NonNegativeFloat = parameter(
        3.47e-7,
        what="cLeaf,m: the leaves' maintenance respiration",
        unit="mg mg⁻¹ s⁻¹",
        source=TABLE_9_1,
    )
    c_stem_m: NonNegativeFloat = parameter(
        1.47e-7,
        what="cStem,m: the stems' maintenance respiration",
        unit="mg mg⁻¹ s⁻¹",
        source=TABLE_9_1,
    )
    c_fruit_g: NonNegativeFloat = parameter(
        0.27,
        what="cFruit,g: the fruit's growth respiration, of its growth",
        unit="-",
        source=TABLE_9_1,
    )
    c_leaf_g: NonNegativeFloat = parameter(
        0.28,
        what="cLeaf,g: the leaves' growth respiration, of their growth",
        unit="-",
        source=TABLE_9_1,
    )
    c_stem_g: NonNegativeFloat = parameter(
        0.3,
        what="cStem,g: the stems' growth respiration, of their growth",
        unit="-",
        source=TABLE_9_1,
    )
    c_rgr: NonNegativeFloat = parameter(
        2.85e6,
        what="cRGR: the maintenance respiration's regression coefficient",
        unit="s (written s⁻¹; cRgr · rgr is dimensionless)",
        source=TABLE_9_1,
    )
    c_buf_max: PositiveFloat = parameter(
        20e3,
        what="cBuf,max: the most carbohydrate in the buffer",
        unit="mg CH₂O m⁻²",
        source=TABLE_9_1,
    )
    c_buf_min: NonNegativeFloat = parameter(
        1e3,
        what="cBuf,min: the least carbohydrate in the buffer",
        unit="mg CH₂O m⁻²",
        source=TABLE_9_1,
    )
    e_j: PositiveFloat = parameter(
        37e3,
        what="EJ: the electron transport's activation energy",
        unit="J mol⁻¹",
        source=TABLE_9_1,
    )
    h: PositiveFloat = parameter(
        22e4,
        what="H: the electron transport's deactivation energy",
        unit="J mol⁻¹",
        source=TABLE_9_1,
    )
    s: PositiveFloat = parameter(
        710.0,
        what="S: the electron transport's entropy",
        unit="J mol⁻¹ K⁻¹",
        source=TABLE_9_1,
    )
    j25_leaf_max: PositiveFloat = parameter(
        210.0,
        what="J25Leaf,max: the most electron transport at 25 °C",
        unit="µmol e⁻ m⁻² leaf s⁻¹",
        source=TABLE_9_1,
    )
    m_ch2o: PositiveFloat = parameter(
        30e-3,
        what="MCH2O: the molar mass of CH₂O",
        unit="mg µmol⁻¹",
        source=TABLE_9_1,
    )
    rg_fruit: NonNegativeFloat = parameter(
        0.328,
        what="rgFruit: the fruit's potential growth",
        unit="mg CH₂O m⁻² s⁻¹",
        source=TABLE_9_1,
    )
    rg_leaf: NonNegativeFloat = parameter(
        0.095,
        what="rgLeaf: the leaves' potential growth",
        unit="mg CH₂O m⁻² s⁻¹",
        source=TABLE_9_1,
    )
    rg_stem: NonNegativeFloat = parameter(
        0.074,
        what="rgStem: the stems' potential growth",
        unit="mg CH₂O m⁻² s⁻¹",
        source=TABLE_9_1,
    )
    sla: PositiveFloat = parameter(
        2.66e-5,
        what="SLA: the specific leaf area",
        unit="m² leaf mg⁻¹",
        source=TABLE_9_1,
    )
    t25k: PositiveFloat = parameter(
        298.15,
        what="T25K: the electron transport's reference temperature",
        unit="K",
        source=TABLE_9_1,
    )
    t_end_sum: PositiveFloat = parameter(
        1035.0,
        what="TEndSum: the temperature sum to a fully generative crop",
        unit="°C day",
        source=f"{TABLE_9_1}, its unit changed as GreenLight's definition notes",
    )
    q10m: PositiveFloat = parameter(
        2.0,
        what="Q10m: the maintenance respiration's rise for each 10 °C",
        unit="-",
        source=TABLE_9_1,
    )
    t_can_min: float = parameter(
        10.0,
        what="TCan,min: the instantaneous temperature below which growth is inhibited",
        unit="°C",
        source=TABLE_9_2,
    )
    t_can_max: float = parameter(
        34.0,
        what="TCan,max: the instantaneous temperature above which growth is inhibited",
        unit="°C",
        source=TABLE_9_2,
    )
    t_can24_min: float = parameter(
        15.0,
        what="TCan24,min: the last day's mean temperature below which growth is inhibited",
        unit="°C",
        source=TABLE_9_2,
    )
    t_can24_max: float = parameter(
        24.5,
        what="TCan24,max: the last day's mean temperature above which growth is inhibited",
        unit="°C",
        source=TABLE_9_2,
    )
    rgr: NonNegativeFloat = parameter(
        3e-6,
        what="RGR: the relative growth rate, a constant, 'assumed'",
        unit="s⁻¹",
        source="GreenLight 1's setGlParams.m, 'assumed', as GreenLight's definition cites it",
    )
    r: PositiveFloat = parameter(
        8314.0,
        what="R: the gas constant",
        unit="J kmol⁻¹ K⁻¹",
        source="Vanthoor (2011), Table 8.1 (Table 9.1 gives 8.314 J mol⁻¹ K⁻¹)",
    )
    c_fruit_max: PositiveFloat = parameter(
        300e3,
        what="cFruit,max: the most fruit unharvested",
        unit="mg CH₂O m⁻²",
        source="Katzin (2021), p. 246",
    )
    k1_par: PositiveFloat = parameter(
        0.7,
        what="K1,PAR: the canopy's extinction of the PAR from above",
        unit="-",
        source=f"Vanthoor (2011), Table 8.1, {EXTENSION}",
    )
    k2_par: PositiveFloat = parameter(
        0.7,
        what="K2,PAR: the canopy's extinction of the PAR reflected from the floor",
        unit="-",
        source=f"Vanthoor (2011), Table 8.1, {EXTENSION}",
    )
    rho_can_par: NonNegativeFloat = parameter(
        0.07,
        what="ρCan,PAR: the canopy's reflection of PAR",
        unit="-",
        source=f"Vanthoor (2011), Table 8.1, {EXTENSION}",
        most=1.0,
        most_from=REFLECTED,
    )
    rho_flr_par: NonNegativeFloat = parameter(
        0.65,
        what="ρFlr,PAR: the floor's reflection of PAR, the Netherlands'",
        unit="-",
        source=f"Vanthoor (2011), Table 8.2, the Netherlands, {EXTENSION}",
        most=1.0,
        most_from=REFLECTED,
    )

    @property
    def c_leaf_max(self) -> float:
        """The most leaf (mg CH₂O m⁻², Eq 9.46)."""
        return self.lai_max / self.sla


class VanthoorState(BaseModel):
    """Its state, per m² of floor: the carbohydrates in the buffer, the
    fruit, the leaves and the stems (mg CH₂O m⁻²); the temperature sum
    (°C day); the canopy's temperature over the last day (°C); and the fruit
    harvested since it was planted (mg CH₂O m⁻²), which is the integral of a
    rate in the reference, kept here as nothing else remembers it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    c_buf: float
    c_fruit: float
    c_leaf: float
    c_stem: float
    t_can_sum: float
    t_can_24: float
    harvested_fruit: float

    def leaf_area_index(self, parameters: VanthoorParameters) -> float:
        """Eq 9.5 (m² leaf m⁻² floor)."""
        return parameters.sla * self.c_leaf


# The state on the first day, as GreenLight starts it.
INITIAL_STATE: Final = VanthoorState(
    c_buf=20e3,
    c_fruit=312.0,
    c_leaf=4368.0,
    c_stem=1560.0,
    t_can_sum=0.0,
    t_can_24=20.5,
    harvested_fruit=0.0,
)
