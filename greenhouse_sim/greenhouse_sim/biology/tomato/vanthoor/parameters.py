"""Vanthoor's model's parameters and its state (decision 0060).

The parameters and the initial state are GreenLight 2.0.7's, as the
reproduction's manifest records each with its unit and source
(`research/reproductions/vanthoor_katzin/manifest.json`). "Table" is that of
Vanthoor's thesis. Each field is named by the published symbol.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveFloat


class VanthoorParameters(BaseModel):
    """The model's parameters, as GreenLight's crop definition and its
    standalone extension give them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # laiMax: the most leaf area (m² leaf m⁻² floor), the Netherlands' (Table 2.2).
    lai_max: PositiveFloat = 3.0
    # alpha: photons to electrons (µmol e⁻ µmol⁻¹ photons, Table 9.1).
    alpha: PositiveFloat = 0.385
    # θ: the curvature of the electron transport (Table 9.1).
    theta: PositiveFloat = 0.7
    # ηCO2,AirStom: the air's CO₂ to the stomata's (Table 9.1).
    eta_co2_air_stom: PositiveFloat = 0.67
    # cΓ: temperature's effect on Γ (µmol mol⁻¹ K⁻¹, Table 9.1).
    c_gamma: NonNegativeFloat = 1.7
    # Maintenance respiration (mg mg⁻¹ s⁻¹, Table 9.1).
    c_fruit_m: NonNegativeFloat = 1.16e-7
    c_leaf_m: NonNegativeFloat = 3.47e-7
    c_stem_m: NonNegativeFloat = 1.47e-7
    # Growth respiration (Table 9.1).
    c_fruit_g: NonNegativeFloat = 0.27
    c_leaf_g: NonNegativeFloat = 0.28
    c_stem_g: NonNegativeFloat = 0.3
    # cRgr: maintenance respiration's regression coefficient (s, Table 9.1,
    # which writes s⁻¹; `c_rgr * rgr` is dimensionless).
    c_rgr: NonNegativeFloat = 2.85e6
    # The buffer's most and least (mg CH₂O m⁻², Table 9.1).
    c_buf_max: PositiveFloat = 20e3
    c_buf_min: NonNegativeFloat = 1e3
    # The electron transport's activation and deactivation (J mol⁻¹) and its
    # entropy (J mol⁻¹ K⁻¹, Table 9.1).
    e_j: PositiveFloat = 37e3
    h: PositiveFloat = 22e4
    s: PositiveFloat = 710.0
    # The most electron transport at 25 °C (µmol e⁻ m⁻² leaf s⁻¹, Table 9.1).
    j25_leaf_max: PositiveFloat = 210.0
    # The molar mass of CH₂O (mg µmol⁻¹, Table 9.1).
    m_ch2o: PositiveFloat = 30e-3
    # Potential growth (mg CH₂O m⁻² s⁻¹, Table 9.1).
    rg_fruit: NonNegativeFloat = 0.328
    rg_leaf: NonNegativeFloat = 0.095
    rg_stem: NonNegativeFloat = 0.074
    # The specific leaf area (m² leaf mg⁻¹ CH₂O, Table 9.1).
    sla: PositiveFloat = 2.66e-5
    # The electron transport's reference temperature (K, Table 9.1).
    t25k: PositiveFloat = 298.15
    # The temperature sum to a fully generative crop (°C day, Table 9.1).
    t_end_sum: PositiveFloat = 1035.0
    # Q10 of maintenance respiration (Table 9.1).
    q10m: PositiveFloat = 2.0
    # The instantaneous temperature's inhibition (°C, Table 9.2).
    t_can_min: float = 10.0
    t_can_max: float = 34.0
    # The last day's temperature's inhibition (°C, Table 9.2).
    t_can24_min: float = 15.0
    t_can24_max: float = 24.5
    # The relative growth rate, a constant, "assumed" (s⁻¹, GreenLight 1).
    rgr: NonNegativeFloat = 3e-6
    # The gas constant (J kmol⁻¹ K⁻¹, Table 8.1).
    r: PositiveFloat = 8314.0
    # The most fruit unharvested (mg CH₂O m⁻², Katzin 2021, p. 246).
    c_fruit_max: PositiveFloat = 300e3
    # The canopy's extinction of PAR, from above and from the floor (Table 8.1).
    k1_par: PositiveFloat = 0.7
    k2_par: PositiveFloat = 0.7
    # The canopy's and the floor's reflection of PAR, the floor's the
    # Netherlands' (Tables 8.1, 8.2).
    rho_can_par: NonNegativeFloat = 0.07
    rho_flr_par: NonNegativeFloat = 0.65

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
