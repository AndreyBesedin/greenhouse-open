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

from greenhouse_sim.biology.parameter_fields import parameter

# Where Oliveira et al.'s tables are, and where the parameters' values come
# from, as the reproduction's manifest says each.
TABLES: Final = "Oliveira et al. v0.4.0, tables/parameters_inputs/"
GNVMAN: Final = (
    f"{TABLES}tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1"
    " gives them where it does"
)
JONES: Final = f"{TABLES}tomgro_i.csv, 'all': Jones et al. 1999, spreadsheet"
GNV_N01: Final = f"{TABLES}tomgro_i.csv, gnv_n01"
# Why a share is at most 1.
ALL_OF_IT: Final = "a share, of all of it at most"


class TomgroParameters(BaseModel):
    """The model's parameters (`gnvman`) and inputs (`gnv_n01`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alpha_f: NonNegativeFloat = parameter(
        0.8,
        what="alpha_F: the share of the day's net growth to the fruit, at most",
        unit="fraction d⁻¹",
        source=GNVMAN,
        most=1.0,
        most_from=f"{ALL_OF_IT}: the fruit grows by it of the day's net growth (growth.py)",
    )
    beta: float = parameter(
        0.169,
        what="β: the leaf expansion's rise with the nodes",
        unit="node⁻¹",
        source=GNVMAN,
    )
    delta: NonNegativeFloat = parameter(
        0.038,
        what="δ: the leaf area added with each node, at most",
        unit="m² leaf node⁻¹",
        source=GNVMAN,
    )
    df_max: NonNegativeFloat = parameter(
        0.08,
        what="DFmax: the fruit's maturing rate, at most",
        unit="d⁻¹",
        source=GNVMAN,
        most=1.0,
        most_from=(
            "the day's step: a day matures DFmax of the fruit not yet mature, all of it at"
            " most (growth.py)"
        ),
    )
    e: PositiveFloat = parameter(
        0.75,
        what="E: the conversion of CH₂O to dry weight",
        unit="g dry weight g⁻¹ CH₂O",
        source=GNVMAN,
    )
    k: PositiveFloat = parameter(
        0.58,
        what="K: the canopy's light extinction coefficient",
        unit="-",
        source=GNVMAN,
    )
    k_f: NonNegativeFloat = parameter(
        5.0,
        what="KF: the nodes between the first fruit and its maturing",
        unit="nodes",
        source=GNVMAN,
    )
    m: NonNegativeFloat = parameter(
        0.1,
        what="m: the leaves' light transmission",
        unit="-",
        source=GNVMAN,
        below=1.0,
        most_from=(
            "a transmission, less than all the light: at 1 an hour with no light's"
            " photosynthesis is 0 / 0 (growth.py)"
        ),
    )
    n_b: float = parameter(
        16.0,
        what="Nb: the nodes at which the leaf expansion turns",
        unit="node",
        source=GNVMAN,
    )
    n_ff: float = parameter(
        22.0,
        what="NFF: the nodes at which the first fruit sets",
        unit="node",
        source=GNVMAN,
    )
    n_max: NonNegativeFloat = parameter(
        0.5,
        what="Nmax: the node rate, at most",
        unit="node d⁻¹",
        source=GNVMAN,
    )
    p_1: NonNegativeFloat = parameter(
        2.0,
        what="p1: the leaf weight lost with each node once the leaf area is full",
        unit="g leaf node⁻¹",
        source=GNVMAN,
    )
    q10: PositiveFloat = parameter(
        1.4,
        what="Q10: the maintenance respiration's rise for each 10 °C",
        unit="-",
        source=GNVMAN,
    )
    qe: NonNegativeFloat = parameter(
        0.08,
        what="Qe: the leaves' quantum efficiency",
        unit="µmol CO₂ µmol⁻¹ photon",
        source=GNVMAN,
    )
    rm: NonNegativeFloat = parameter(
        0.016,
        what="rm: the maintenance respiration",
        unit="d⁻¹, applied as rm / 24 an hour",
        source=GNVMAN,
    )
    sl_n1: float = parameter(
        0.025,
        what="slN1: the node rate's rise with the temperature",
        unit="°C⁻¹",
        source=GNVMAN,
    )
    sl_n2: float = parameter(
        0.05,
        what="slN2: the node rate's fall with the temperature",
        unit="°C⁻¹",
        source=GNVMAN,
    )
    sl_r: float = parameter(
        0.0032,
        what="slR: the roots' share's fall with the nodes",
        unit="node⁻¹",
        source=GNVMAN,
    )
    t_crit: float = parameter(
        24.4,
        what="Tcrit: the daytime temperature above which fruit sets less",
        unit="°C",
        source=GNVMAN,
    )
    tau1: NonNegativeFloat = parameter(
        0.07428,
        what="τ1: the leaves' maximum photosynthesis's rise with the CO₂, below 350 ppm",
        unit="µmol m⁻² s⁻¹ ppm⁻¹",
        source=GNVMAN,
    )
    tau2: NonNegativeFloat = parameter(
        0.05848,
        what="τ2: the leaves' maximum photosynthesis's rise with the CO₂, above 350 ppm",
        unit="µmol m⁻² s⁻¹ ppm⁻¹",
        source=GNVMAN,
    )
    tmax_pg: float = parameter(
        35.0,
        what="tmaxPg: the temperature above which photosynthesis falls",
        unit="°C",
        source=GNVMAN,
    )
    tmin_fr_gr: float = parameter(
        8.5,
        what="tmin_fr_gr: the temperature below which fruit grows no more",
        unit="°C",
        source=GNVMAN,
    )
    t_slop: PositiveFloat = parameter(
        20.6,
        what="TSlop: the leaf expansion's fall with the daytime temperature",
        unit="°C",
        source=GNVMAN,
    )
    v: NonNegativeFloat = parameter(
        0.135,
        what="V: the fruit's share's rise with the nodes past the first fruit",
        unit="node⁻¹",
        source=GNVMAN,
    )
    v_max: NonNegativeFloat = parameter(
        8.0,
        what="Vmax: the dry weight added with each node, at most",
        unit="g dry weight node⁻¹",
        source=GNVMAN,
    )
    d: PositiveFloat = parameter(
        2.5926912,
        what=(
            "D, an input: the conversion of gross photosynthesis from µmol CO₂ m⁻² s⁻¹ to"
            " g CH₂O m⁻² d⁻¹"
        ),
        unit="g CH₂O s d⁻¹ µmol⁻¹ CO₂",
        source=JONES,
    )
    trgh: NonNegativeFloat = parameter(
        1.0,
        what=(
            "TRGH, an input: the greenhouse's light transmission, 1 where the PPFD given is"
            " inside the greenhouse already, as the run's is"
        ),
        unit="-",
        source=(
            f"{TABLES}tomgro_i.csv, 'all': transmissivity of the cover, Jones et al. 1999,"
            " spreadsheet (inferred)"
        ),
        most=1.0,
        most_from=f"{ALL_OF_IT}: the light the cover lets through of the light outside",
    )
    lai_max: PositiveFloat = parameter(
        4.0,
        what="LAImax, an input: the leaf area index, at most",
        unit="m² leaf m⁻²",
        source=GNV_N01,
    )
    ro: PositiveFloat = parameter(
        3.5,
        what="ρ, an input: the plants per m² of floor the parameters are for",
        unit="plants m⁻²",
        source=GNV_N01,
    )


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
