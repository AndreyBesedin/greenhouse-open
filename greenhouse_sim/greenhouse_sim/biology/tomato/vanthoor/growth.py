"""Vanthoor's model's rates and its hour (decision 0060).

`rates` gives each state's rate of change at a moment, from the canopy's
temperature, the PAR above the canopy and the CO₂. `live_hour` integrates
them through an hour whose drivers run straight from one value to another.

It takes twelve steps of the classic four stages an hour, in plain floats.
The reference uses scipy's BDF, whose steps depend on all before them; a
model's hour here depends on its state and its drivers alone, as a rung's
must, and adds no dependency to the package. Twelve is where the states have
converged: on the reproduction's season, its answers at 60 steps an hour are
the same within 0.013 of each state's tolerance, and each state is within
0.09 of its tolerance of the converged reference, which is the reference's
own solver's spread (its README). Six steps reach 0.21 of a tolerance, four
1.05.
"""

import math
from collections.abc import Sequence
from typing import Final

from greenhouse_sim.biology.area_contract import HourDrivers
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters, VanthoorState
from greenhouse_sim.units import DAY_S, HOUR_S

STEPS_AN_HOUR: Final = 12
# The classic four stages' weights add up to this.
STAGE_WEIGHTS: Final = 6
KELVIN_AT_0_C: Final = 273.15
# R is in J kmol⁻¹ K⁻¹ (Table 8.1); the electron transport's Arrhenius form
# takes it per mol.
PER_KMOL: Final = 1e-3
# Electrons per CO₂ fixed (Eq 9.12), and the CO₂ compensation point's
# reference temperature (°C, Eq 9.23).
ELECTRONS_PER_CO2: Final = 4.0
GAMMA_REFERENCE_C: Final = 20.0
# The quadratic formula's 4, in the electron transport's hyperbola (Eq 9.14).
HYPERBOLA_DISCRIMINANT: Final = 4.0
# Eq 9.28: the canopy's last day's temperature on structural growth.
GROWTH_PER_C: Final = 0.047
GROWTH_AT_0_C: Final = 0.06
# The smooth switches (Section 9.7.2, Table 9.2): their steepness.
BUFFER_FULL_STEEPNESS: Final = 5e-4
BUFFER_EMPTY_STEEPNESS: Final = 5e-3
TCAN_LOW_STEEPNESS: Final = 0.869
TCAN_HIGH_STEEPNESS: Final = 0.5793
TCAN24_LOW_STEEPNESS: Final = 1.1587
TCAN24_HIGH_STEEPNESS: Final = 1.3904
TCANSUM_SMOOTHING: Final = 1e-4
# Maintenance respiration's Q10 reference (°C, Eq 9.45).
Q10_REFERENCE_C: Final = 25.0
Q10_PER_C: Final = 0.1
# Katzin (2021) Eq 7.45: a harvest's smoothing and its most rate, of the
# leaves (Katzin (2021)'s dataset's 1e5, not the published 5e4) and the
# fruit.
HARVEST_SHARPNESS: Final = 2 * math.log(100)
LEAF_HARVEST_SMOOTHING: Final = 1e4
LEAF_HARVEST_MOST: Final = 1e5
FRUIT_HARVEST_SMOOTHING: Final = 1e4
FRUIT_HARVEST_MOST: Final = 5e4


def _logistic(steepness: float, x: float) -> float:
    return 1 / (1 + math.exp(-steepness * x))


def _harvest(amount: float, most_unharvested: float, smoothing: float, most_rate: float) -> float:
    """Katzin (2021) Eq 7.45: a harvest's rate, rising smoothly as the
    amount passes the most left unharvested (mg CH₂O m⁻² s⁻¹)."""
    return most_rate / (1 + math.exp(-(amount - most_unharvested) * HARVEST_SHARPNESS / smoothing))


def fruit_harvest(c_fruit: float, p: VanthoorParameters) -> float:
    """The fruit's harvest rate at `c_fruit` (mg CH₂O m⁻² s⁻¹)."""
    return _harvest(c_fruit, p.c_fruit_max, FRUIT_HARVEST_SMOOTHING, FRUIT_HARVEST_MOST)


def _smooth_ramp(x: float) -> float:
    """Eq 9.27, B.6: 0 for a negative `x` and `x` for a positive one, with
    its corner rounded off."""
    return (x + math.sqrt(x**2 + TCANSUM_SMOOTHING)) / 2


def _absorbed_par(par_above: float, lai: float, p: VanthoorParameters) -> float:
    """Eq 9.17 to 9.19: the PAR the canopy absorbs, from above and reflected
    from the floor (µmol m⁻² s⁻¹)."""
    entering = par_above * (1 - p.rho_can_par)
    passing = math.exp(-p.k1_par * lai)
    from_floor = p.rho_flr_par * entering * passing * (1 - math.exp(-p.k2_par * lai))
    return entering * (1 - passing) + from_floor


def _assimilation(
    temperature_c: float, par_can: float, co2_ppm: float, lai: float, p: VanthoorParameters
) -> float:
    """Eq 9.12 to 9.23: photosynthesis less photorespiration (µmol CO₂ m⁻²
    s⁻¹). None with no leaves or no CO₂, where the equations are undefined."""
    if lai <= 0.0 or co2_ppm <= 0.0:
        return 0.0
    t_k = temperature_c + KELVIN_AT_0_C
    r = PER_KMOL * p.r
    j25_canopy = lai * p.j25_leaf_max
    j_potential = (
        j25_canopy
        * math.exp(p.e_j * (t_k - p.t25k) / (r * t_k * p.t25k))
        * (1 + math.exp((p.s * p.t25k - p.h) / (r * p.t25k)))
        / (1 + math.exp((p.s * t_k - p.h) / (r * t_k)))
    )
    light = p.alpha * par_can
    j = (1 / (2 * p.theta)) * (
        j_potential
        + light
        - math.sqrt(
            (j_potential + light) ** 2 - HYPERBOLA_DISCRIMINANT * p.theta * j_potential * light
        )
    )
    co2_stomata = p.eta_co2_air_stom * co2_ppm
    leaf_share = p.j25_leaf_max / j25_canopy
    gamma = leaf_share * p.c_gamma * temperature_c + GAMMA_REFERENCE_C * p.c_gamma * (
        1 - leaf_share
    )
    gross = j * (co2_stomata - gamma) / (ELECTRONS_PER_CO2 * (co2_stomata + 2 * gamma))
    return gross - gross * gamma / co2_stomata


def rates(
    state: Sequence[float],
    temperature_c: float,
    par_above: float,
    co2_ppm: float,
    p: VanthoorParameters,
) -> list[float]:
    """Each value's rate of change, per s, of `state`, in `VanthoorState`'s
    order."""
    c_buf, c_fruit, c_leaf, c_stem, t_can_sum, t_can_24, _ = state
    lai = p.sla * c_leaf

    filling = _logistic(-BUFFER_FULL_STEEPNESS, c_buf - p.c_buf_max)
    assimilated = (
        p.m_ch2o
        * filling
        * _assimilation(temperature_c, _absorbed_par(par_above, lai, p), co2_ppm, lai, p)
    )

    drawing = _logistic(BUFFER_EMPTY_STEEPNESS, c_buf - p.c_buf_min)
    instant = _logistic(TCAN_LOW_STEEPNESS, temperature_c - p.t_can_min) * _logistic(
        -TCAN_HIGH_STEEPNESS, temperature_c - p.t_can_max
    )
    last_day = _logistic(TCAN24_LOW_STEEPNESS, t_can_24 - p.t_can24_min) * _logistic(
        -TCAN24_HIGH_STEEPNESS, t_can_24 - p.t_can24_max
    )
    generative = _smooth_ramp(t_can_sum / p.t_end_sum) - _smooth_ramp(
        (t_can_sum - p.t_end_sum) / p.t_end_sum
    )
    growth = GROWTH_PER_C * t_can_24 + GROWTH_AT_0_C
    to_fruit = drawing * instant * last_day * generative * growth * p.rg_fruit
    to_leaf = drawing * last_day * growth * p.rg_leaf
    to_stem = drawing * last_day * growth * p.rg_stem
    growth_respiration = p.c_leaf_g * to_leaf + p.c_stem_g * to_stem + p.c_fruit_g * to_fruit

    maintenance = (1 - math.exp(-p.c_rgr * p.rgr)) * p.q10m ** (
        Q10_PER_C * (t_can_24 - Q10_REFERENCE_C)
    )
    harvested = fruit_harvest(c_fruit, p)
    pruned = _harvest(c_leaf, p.c_leaf_max, LEAF_HARVEST_SMOOTHING, LEAF_HARVEST_MOST)
    return [
        assimilated - to_fruit - to_leaf - to_stem - growth_respiration,
        to_fruit - maintenance * c_fruit * p.c_fruit_m - harvested,
        to_leaf - maintenance * c_leaf * p.c_leaf_m - pruned,
        to_stem - maintenance * c_stem * p.c_stem_m,
        temperature_c / DAY_S,
        (temperature_c - t_can_24) / DAY_S,
        harvested,
    ]


def live_hour(
    state: VanthoorState,
    start: HourDrivers,
    end: HourDrivers,
    p: VanthoorParameters,
    *,
    steps: int = STEPS_AN_HOUR,
) -> VanthoorState:
    """`state` after an hour whose drivers run straight from `start` to
    `end`, in `steps` steps."""
    h = HOUR_S / steps

    def drivers_at(share: float) -> tuple[float, float, float]:
        return (
            start.temperature_c + share * (end.temperature_c - start.temperature_c),
            start.par_above_umol_m2_s
            + share * (end.par_above_umol_m2_s - start.par_above_umol_m2_s),
            start.co2_ppm + share * (end.co2_ppm - start.co2_ppm),
        )

    values = list(state.model_dump().values())
    for step in range(steps):
        at_start = drivers_at(step / steps)
        halfway = drivers_at((2 * step + 1) / (2 * steps))
        at_end = drivers_at((step + 1) / steps)
        k1 = rates(values, *at_start, p)
        k2 = rates([v + h / 2 * r for v, r in zip(values, k1, strict=True)], *halfway, p)
        k3 = rates([v + h / 2 * r for v, r in zip(values, k2, strict=True)], *halfway, p)
        k4 = rates([v + h * r for v, r in zip(values, k3, strict=True)], *at_end, p)
        values = [
            v + h / STAGE_WEIGHTS * (a + 2 * b + 2 * c + d)
            for v, a, b, c, d in zip(values, k1, k2, k3, k4, strict=True)
        ]
    return VanthoorState(**dict(zip(VanthoorState.model_fields, values, strict=True)))
