"""Reduced-State TOMGRO's day (decision 0060): its five states after a day
of hours, each hour's air temperature, PPFD and CO₂.

Gross photosynthesis, maintenance respiration and the node rate are worked
out for each of the day's 24 hours, from the hour's temperature and PPFD,
and summed; the CO₂ is read from the day's first hour, as the reference
reads it. The states are updated once, in a fixed order, each later rate
seeing those updated before it: the nodes, the leaf area index, the mature
fruit, the fruit, and the weight above ground. The forms and their fixed
constants are the spreadsheet's, as Oliveira et al. write them.
"""

import math
from collections.abc import Sequence
from typing import Final

from greenhouse_sim.biology.area_contract import HourDrivers
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters, TomgroState
from greenhouse_sim.units import HOURS_A_DAY

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


def _photosynthesis_reduction(temperature_c: float, most_c: float) -> float:
    """PGRED: photosynthesis reduced by too cold or too hot an hour."""
    rising = 1.0 / (1.0 + PGRED_SCALE * math.exp(-PGRED_STEEPNESS * (temperature_c - PGRED_LOW_C)))
    falling = 1.0 - 1.0 / (
        1.0 + PGRED_SCALE * math.exp(-PGRED_STEEPNESS * (temperature_c - most_c))
    )
    return min(rising, falling)


def _node_rate_factor(temperature_c: float, p: TomgroParameters) -> float:
    """fN(T): the node rate's response to an hour's temperature."""
    return min(
        NODE_RATE_BASE + p.sl_n1 * temperature_c, NODE_RATE_HIGH - p.sl_n2 * temperature_c, 1.0
    )


def _daytime_c(hours: Sequence[HourDrivers]) -> float:
    """The mean temperature of the day's hours with light; of hours 6 to 19,
    with none."""
    lit = [hour.temperature_c for hour in hours if hour.par_above_umol_m2_s > 0]
    if not lit:
        lit = [
            hour.temperature_c
            for number, hour in enumerate(hours)
            if DAYTIME_FROM_HOUR <= number <= DAYTIME_TO_HOUR
        ]
    return sum(lit) / len(lit)


def _leaf_maximum(co2_ppm: float, p: TomgroParameters) -> float:
    """LFmax: the leaves' maximum photosynthesis (µmol m⁻² s⁻¹), rounded to
    a whole number, half to even, as the spreadsheet rounds it."""
    if co2_ppm <= CO2_KNEE_PPM:
        rate = p.tau1 * co2_ppm
    else:
        rate = p.tau1 * CO2_KNEE_PPM + p.tau2 * (co2_ppm - CO2_KNEE_PPM)
    return float(round(rate))


def net_growth(state: TomgroState, hours: Sequence[HourDrivers], p: TomgroParameters) -> float:
    """The day's net growth above ground (g dry weight m⁻²): the hours'
    gross photosynthesis less their maintenance respiration, converted at
    the efficiency `E`, less the roots' share."""
    leaf_maximum = _leaf_maximum(hours[0].co2_ppm, p)
    canopy = (1 - p.m) * leaf_maximum
    living = state.w - state.wm
    total = 0.0
    for hour in hours:
        light = p.qe * p.k * hour.par_above_umol_m2_s * p.trgh
        gross = (
            p.d
            / HOURS_A_DAY
            * leaf_maximum
            * _photosynthesis_reduction(hour.temperature_c, p.tmax_pg)
            / p.k
            * math.log((canopy + light) / (canopy + light * math.exp(-p.k * state.lai)))
        )
        respiration = (
            p.q10 ** ((hour.temperature_c - Q10_BASE_C) * Q10_PER_C) * (p.rm / HOURS_A_DAY) * living
        )
        total += gross - respiration
    roots = max(ROOT_SHARE_START - p.sl_r * state.n, ROOT_SHARE_LEAST)
    return p.e * total * (1 - roots)


def live_day(state: TomgroState, hours: Sequence[HourDrivers], p: TomgroParameters) -> TomgroState:
    """The states after one day of `hours`, 24 of them from the day's
    start."""
    if len(hours) != HOURS_A_DAY:
        raise ValueError(f"a day is {HOURS_A_DAY} hours, not {len(hours)}")
    net = net_growth(state, hours, p)
    mean_c = sum(hour.temperature_c for hour in hours) / HOURS_A_DAY
    daytime_c = _daytime_c(hours)

    node_rate = p.n_max / HOURS_A_DAY * sum(_node_rate_factor(h.temperature_c, p) for h in hours)
    n = state.n + node_rate

    if state.lai <= p.lai_max:
        expansion = min((LEAF_EXPANSION_HOT_C - daytime_c) / p.t_slop, 1.0)
        rising = math.exp(p.beta * (state.n - p.n_b))
        lai_rate = p.ro * p.delta * expansion * rising * node_rate / (1 + rising)
    else:
        lai_rate = 0.0
    lai = min(state.lai + lai_rate, p.lai_max)

    if n > p.n_ff + p.k_f:
        maturing = max(0.0, min(1.0, MATURING_SLOPE * (mean_c - MATURING_BASE_C)))
        mature_rate = p.df_max * (state.wf - state.wm) * maturing
    else:
        mature_rate = 0.0
    wm = state.wm + mature_rate

    if n > p.n_ff:
        cold = max(0.0, min(1.0, FRUIT_SET_SLOPE * (mean_c - p.tmin_fr_gr)))
        heat = max(FRUIT_HEAT_LEAST, min(1.0, 1 - FRUIT_HEAT_SLOPE * (daytime_c - p.t_crit)))
        fruit_rate = net * p.alpha_f * cold * (1 - math.exp(-p.v * (n - p.n_ff))) * heat
    else:
        fruit_rate = 0.0
    wf = state.wf + fruit_rate

    leaf_weight = 0.0 if lai < p.lai_max else p.p_1
    weight_rate = min(
        net - leaf_weight * p.ro * node_rate,
        fruit_rate + (p.v_max - leaf_weight) * p.ro * node_rate,
    )
    w = state.w + weight_rate
    return TomgroState(n=n, lai=lai, w=w, wf=wf, wm=wm)
