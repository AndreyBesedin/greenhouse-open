"""Reduced-State TOMGRO, implemented on its own, for its reproduction.

Jones, Kenig and Vallejos (1999, doi:10.13031/2013.13203) reduce TOMGRO to
five states: the main stem's nodes `n`, the leaf area index `lai`, and the
dry weights above ground `w`, of the fruit `wf` and of the mature fruit
`wm`, each per m². The variant reproduced is Oliveira et al.'s (decision
0060): the paper's and Jones et al. (1991)'s forms, with those of Jones's
spreadsheet where they differ, as that implementation documents them
(`docs/research/reduced-tomgro-inventory.md`). It is written from those
equations, not from the reference's code, in plain Python floats.

The states are updated once a day. Gross photosynthesis, maintenance
respiration and the node rate are worked out for each of the day's 24
hours, from the hour's air temperature and PPFD, and summed; CO₂ is read
from the day's first hour. The states are updated in a fixed order, each
later rate seeing the states updated before it: `n`, `lai`, `wm`, `wf`,
`w`. Nothing here depends on the simulator.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

HOURS: Final = 24
# The CO₂ below which the leaves' maximum photosynthesis rises along one
# line, above it along another (ppm).
CO2_KNEE_PPM: Final = 350.0
# The temperature responses' fixed constants, as the spreadsheet writes
# them.
PGRED_LOW_C: Final = 10.0
PGRED_STEEPNESS: Final = 0.5
PGRED_SCALE: Final = 9.0
NODE_RATE_BASE: Final = 0.25
NODE_RATE_HIGH: Final = 2.5
ROOT_SHARE_START: Final = 0.18
ROOT_SHARE_LEAST: Final = 0.02
LEAF_EXPANSION_HOT_C: Final = 45.0
FRUIT_SET_SLOPE: Final = 0.0625
FRUIT_HEAT_SLOPE: Final = 0.154
FRUIT_HEAT_LEAST: Final = 0.09
MATURING_SLOPE: Final = 0.0714
MATURING_BASE_C: Final = 9.0
Q10_BASE_C: Final = 20.0
Q10_PER_C: Final = 0.1
# With no hour of light, the daytime is these hours, both included.
DAYTIME_FROM_HOUR: Final = 6
DAYTIME_TO_HOUR: Final = 19


@dataclass(frozen=True)
class Hour:
    """One hour of the drivers: its number in the day, its mean air
    temperature (°C), its mean PPFD inside the greenhouse (µmol m⁻² s⁻¹)
    and its CO₂ (ppm)."""

    hour: int
    temperature_c: float
    ppfd: float
    co2_ppm: float


@dataclass(frozen=True)
class State:
    """The five states, each per m²: nodes, leaf area index (m² m⁻²), and
    dry weights above ground, of the fruit and of the mature fruit
    (g m⁻²)."""

    n: float
    lai: float
    w: float
    wf: float
    wm: float


def _photosynthesis_reduction(temperature_c: float, most_c: float) -> float:
    """PGRED: photosynthesis reduced by too cold or too hot an hour."""
    rising = 1.0 / (1.0 + PGRED_SCALE * math.exp(-PGRED_STEEPNESS * (temperature_c - PGRED_LOW_C)))
    falling = 1.0 - 1.0 / (
        1.0 + PGRED_SCALE * math.exp(-PGRED_STEEPNESS * (temperature_c - most_c))
    )
    return min(rising, falling)


def _node_rate_factor(temperature_c: float, p: Mapping[str, float]) -> float:
    """fN(T): the node rate's response to an hour's temperature."""
    return min(
        NODE_RATE_BASE + p["sl_N1"] * temperature_c,
        NODE_RATE_HIGH - p["sl_N2"] * temperature_c,
        1.0,
    )


def _daytime_c(hours: Sequence[Hour]) -> float:
    """The mean temperature of the day's hours with light; of hours 6 to 19,
    with none."""
    lit = [hour.temperature_c for hour in hours if hour.ppfd > 0]
    if not lit:
        lit = [
            hour.temperature_c
            for hour in hours
            if DAYTIME_FROM_HOUR <= hour.hour <= DAYTIME_TO_HOUR
        ]
    return sum(lit) / len(lit)


def _leaf_maximum(co2_ppm: float, p: Mapping[str, float]) -> float:
    """LFmax: the leaves' maximum photosynthesis (µmol m⁻² s⁻¹), rounded to
    a whole number, half to even, as the spreadsheet rounds it."""
    if co2_ppm <= CO2_KNEE_PPM:
        rate = p["tau1"] * co2_ppm
    else:
        rate = p["tau1"] * CO2_KNEE_PPM + p["tau2"] * (co2_ppm - CO2_KNEE_PPM)
    return float(round(rate))


def net_growth(
    state: State, hours: Sequence[Hour], p: Mapping[str, float], i: Mapping[str, float]
) -> float:
    """The day's net growth above ground (g dry weight m⁻²): the hours'
    gross photosynthesis less their maintenance respiration, converted at
    the efficiency `E`, less the roots' share."""
    leaf_maximum = _leaf_maximum(hours[0].co2_ppm, p)
    canopy = (1 - p["m"]) * leaf_maximum
    living = state.w - state.wm
    total = 0.0
    for hour in hours:
        light = p["Qe"] * p["K"] * hour.ppfd * i["TRGH"]
        gross = (
            i["D"]
            / HOURS
            * leaf_maximum
            * _photosynthesis_reduction(hour.temperature_c, p["tmaxPg"])
            / p["K"]
            * math.log((canopy + light) / (canopy + light * math.exp(-p["K"] * state.lai)))
        )
        respiration = (
            p["Q10"] ** ((hour.temperature_c - Q10_BASE_C) * Q10_PER_C) * (p["rm"] / HOURS) * living
        )
        total += gross - respiration
    roots = max(ROOT_SHARE_START - p["sl_R"] * state.n, ROOT_SHARE_LEAST)
    return p["E"] * total * (1 - roots)


def live_day(
    state: State, hours: Sequence[Hour], p: Mapping[str, float], i: Mapping[str, float]
) -> State:
    """The states after one day of `hours` (24 of them)."""
    if len(hours) != HOURS:
        raise ValueError(f"a day is {HOURS} hours, not {len(hours)}")
    net = net_growth(state, hours, p, i)
    mean_c = sum(hour.temperature_c for hour in hours) / HOURS
    daytime_c = _daytime_c(hours)

    node_rate = p["N_max"] / HOURS * sum(_node_rate_factor(h.temperature_c, p) for h in hours)
    n = state.n + node_rate

    if state.lai <= i["LAI_max"]:
        expansion = min((LEAF_EXPANSION_HOT_C - daytime_c) / p["TSlop"], 1.0)
        rising = math.exp(p["beta"] * (state.n - p["N_b"]))
        lai_rate = i["ro"] * p["delta"] * expansion * rising * node_rate / (1 + rising)
    else:
        lai_rate = 0.0
    lai = min(state.lai + lai_rate, i["LAI_max"])

    if n > p["N_FF"] + p["K_F"]:
        maturing = max(0.0, min(1.0, MATURING_SLOPE * (mean_c - MATURING_BASE_C)))
        mature_rate = p["DFmax"] * (state.wf - state.wm) * maturing
    else:
        mature_rate = 0.0
    wm = state.wm + mature_rate

    if n > p["N_FF"]:
        cold = max(0.0, min(1.0, FRUIT_SET_SLOPE * (mean_c - p["tmin_fr_gr"])))
        heat = max(FRUIT_HEAT_LEAST, min(1.0, 1 - FRUIT_HEAT_SLOPE * (daytime_c - p["T_crit"])))
        fruit_rate = net * p["alpha_F"] * cold * (1 - math.exp(-p["V"] * (n - p["N_FF"]))) * heat
    else:
        fruit_rate = 0.0
    wf = state.wf + fruit_rate

    leaf_weight = 0.0 if lai < i["LAI_max"] else p["p_1"]
    weight_rate = min(
        net - leaf_weight * i["ro"] * node_rate,
        fruit_rate + (p["V_max"] - leaf_weight) * i["ro"] * node_rate,
    )
    w = state.w + weight_rate
    return State(n=n, lai=lai, w=w, wf=wf, wm=wm)


def run(
    days: Sequence[Sequence[Hour]],
    initial: State,
    p: Mapping[str, float],
    i: Mapping[str, float],
) -> list[State]:
    """The states on each day, from the initial ones on day 0."""
    states = [initial]
    for hours in days:
        states.append(live_day(states[-1], hours, p, i))
    return states
