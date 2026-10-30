"""Reduced-State TOMGRO's parameters, its inputs and its state (decision
0060).

The parameters are Oliveira et al.'s set `gnvman` ('original', release
v0.4.0, `tables/parameters_inputs/tomgro_p.csv`), the inputs their set
`gnv_n01`, and the initial state theirs, as the reproduction's manifest
records each with its unit and source
(`research/reproductions/reduced_tomgro/manifest.json`). Each field is named
by the published symbol, in lower case.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveFloat


class TomgroParameters(BaseModel):
    """The model's parameters (`gnvman`) and inputs (`gnv_n01`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # alpha_F: the share of the day's net growth to the fruit, at most (d⁻¹).
    alpha_f: NonNegativeFloat = 0.8
    # β: the leaf expansion's rise with the nodes (node⁻¹).
    beta: float = 0.169
    # δ: the leaf area added with each node, at most (m² leaf node⁻¹).
    delta: NonNegativeFloat = 0.038
    # DFmax: the fruit's maturing rate, at most (d⁻¹).
    df_max: NonNegativeFloat = 0.08
    # E: the conversion of CH₂O to dry weight (g dry weight g⁻¹ CH₂O).
    e: PositiveFloat = 0.75
    # K: the canopy's light extinction coefficient.
    k: PositiveFloat = 0.58
    # KF: the nodes between the first fruit and its maturing (nodes).
    k_f: NonNegativeFloat = 5.0
    # m: the leaves' light transmission.
    m: NonNegativeFloat = 0.1
    # Nb: the nodes at which the leaf expansion turns (node).
    n_b: float = 16.0
    # NFF: the nodes at which the first fruit sets (node).
    n_ff: float = 22.0
    # Nmax: the node rate, at most (node d⁻¹).
    n_max: NonNegativeFloat = 0.5
    # p1: the leaf weight lost with each node once the leaf area is full
    # (g leaf node⁻¹).
    p_1: NonNegativeFloat = 2.0
    # Q10: the maintenance respiration's rise for each 10 °C.
    q10: PositiveFloat = 1.4
    # Qe: the leaves' quantum efficiency (µmol CO₂ µmol⁻¹ photon).
    qe: NonNegativeFloat = 0.08
    # rm: the maintenance respiration (d⁻¹, applied as rm / 24 an hour).
    rm: NonNegativeFloat = 0.016
    # slN1, slN2: the node rate's rise and fall with the temperature (°C⁻¹).
    sl_n1: float = 0.025
    sl_n2: float = 0.05
    # slR: the roots' share's fall with the nodes (node⁻¹).
    sl_r: float = 0.0032
    # Tcrit: the daytime temperature above which fruit sets less (°C).
    t_crit: float = 24.4
    # τ1, τ2: the leaves' maximum photosynthesis's rise with the CO₂, below
    # and above 350 ppm (µmol m⁻² s⁻¹ ppm⁻¹).
    tau1: NonNegativeFloat = 0.07428
    tau2: NonNegativeFloat = 0.05848
    # tmaxPg: the temperature above which photosynthesis falls (°C).
    tmax_pg: float = 35.0
    # tmin_fr_gr: the temperature below which fruit grows no more (°C).
    tmin_fr_gr: float = 8.5
    # TSlop: the leaf expansion's fall with the daytime temperature (°C).
    t_slop: PositiveFloat = 20.6
    # V: the fruit's share's rise with the nodes past the first fruit
    # (node⁻¹).
    v: NonNegativeFloat = 0.135
    # Vmax: the dry weight added with each node, at most (g node⁻¹).
    v_max: NonNegativeFloat = 8.0
    # Inputs. D: the conversion of gross photosynthesis from
    # µmol CO₂ m⁻² s⁻¹ to g CH₂O m⁻² d⁻¹.
    d: PositiveFloat = 2.5926912
    # TRGH: the greenhouse's light transmission, 1 where the PPFD given is
    # inside the greenhouse already, as the run's is.
    trgh: NonNegativeFloat = 1.0
    # LAImax: the leaf area index, at most (m² leaf m⁻²).
    lai_max: PositiveFloat = 4.0
    # ρ: the plants per m² of floor the parameters are for (plants m⁻²).
    ro: PositiveFloat = 3.5


class TomgroState(BaseModel):
    """The five states, each per m² of floor: the main stem's nodes, the
    leaf area index (m² leaf m⁻²), and the dry weights above ground, of the
    fruit and of the mature fruit (g m⁻²)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n: float
    lai: float
    w: float
    wf: float
    wm: float


# The state on the first day, as Oliveira et al. start it.
INITIAL_STATE: Final = TomgroState(n=4.0, lai=0.014, w=0.09, wf=0.0, wm=0.0)
