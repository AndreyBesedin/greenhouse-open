"""Vanthoor's tomato model as Katzin simplified it, implemented on its own.

The variant is GreenLight's (decision 0060): Vanthoor (2011, chapter 9)
with Katzin (2021)'s simplifications, as GreenLight 2.0.7's crop
definition and standalone extension write them
(`docs/research/vanthoor-katzin-inventory.md`). It is written from those
equations, not from GreenLight's code, in plain Python floats.

Six states, each a rate of change in time (s): the carbohydrates in the
buffer, the fruit, the leaves and the stems (mg CH₂O m⁻²), the temperature
sum (°C day) and the canopy's temperature over the last day (°C), a
first-order filter. The leaf area index is derived from the leaves. The
drivers are the canopy's temperature, the PAR above the canopy and the
CO₂; the PAR the canopy absorbs is worked out from the first, as the
standalone extension does.

`run` solves the states as the reference does: scipy's BDF with the same
step limit and tolerances, its dense output left aside, and every output
interpolated linearly onto the hourly grid. Nothing here depends on the
simulator.
"""

import bisect
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from scipy.integrate import solve_ivp

# The states, in the order the definition gives them.
STATES: Final = ("cBuf", "cFruit", "cLeaf", "cStem", "tCanSum", "tCan24")
DAY_S: Final = 86400.0
KELVIN_AT_0_C: Final = 273.15
# R is in J kmol⁻¹ K⁻¹ (Table 8.1); the electron transport's Arrhenius form
# takes it per mol.
PER_KMOL: Final = 1e-3
# Electrons per CO₂ fixed (Eq 9.12), and the CO₂ compensation point's
# reference temperature (°C, Eq 9.23).
ELECTRONS_PER_CO2: Final = 4.0
GAMMA_REFERENCE_C: Final = 20.0
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


@dataclass(frozen=True)
class Drivers:
    """The drivers at their moments (s), each interpolated linearly between
    them, as the reference interpolates them."""

    times: Sequence[float]
    t_can: Sequence[float]
    par_gh: Sequence[float]
    co2_ppm: Sequence[float]

    def at(self, t: float) -> tuple[float, float, float]:
        """The canopy's temperature (°C), the PAR above it (µmol m⁻² s⁻¹)
        and the CO₂ (ppm) at `t`. Up to the second moment, and past the
        last, the reference holds its first and last values: it
        interpolates only from the interval its search for `t` places
        second."""
        j = bisect.bisect_left(self.times, t) - 1
        if j <= 0:
            return self.t_can[0], self.par_gh[0], self.co2_ppm[0]
        if j >= len(self.times) - 1:
            return self.t_can[-1], self.par_gh[-1], self.co2_ppm[-1]
        d = (t - self.times[j]) / (self.times[j + 1] - self.times[j])
        return (
            (1 - d) * self.t_can[j] + d * self.t_can[j + 1],
            (1 - d) * self.par_gh[j] + d * self.par_gh[j + 1],
            (1 - d) * self.co2_ppm[j] + d * self.co2_ppm[j + 1],
        )


@dataclass(frozen=True)
class Solver:
    """scipy's `solve_ivp` settings: the method, the longest step (s) and
    the tolerances."""

    method: str
    max_step: float
    atol: float
    rtol: float


def _logistic(steepness: float, x: float) -> float:
    return 1 / (1 + math.exp(-steepness * x))


def leaf_area_index(c_leaf: float, p: Mapping[str, float]) -> float:
    """Eq 9.5 (m² leaf m⁻² floor)."""
    return p["sla"] * c_leaf


def _harvest(amount: float, most_unharvested: float, smoothing: float, most_rate: float) -> float:
    """Katzin (2021) Eq 7.45: a harvest's rate, rising smoothly as the
    amount passes the most left unharvested (mg CH₂O m⁻² s⁻¹)."""
    return most_rate / (1 + math.exp(-(amount - most_unharvested) * HARVEST_SHARPNESS / smoothing))


def fruit_harvest(c_fruit: float, p: Mapping[str, float]) -> float:
    return _harvest(c_fruit, p["cFruitMax"], FRUIT_HARVEST_SMOOTHING, FRUIT_HARVEST_MOST)


def _leaf_harvest(c_leaf: float, p: Mapping[str, float]) -> float:
    """Eq 9.46 and 9.47, B.5: the leaves pruned past the most leaf area."""
    return _harvest(c_leaf, p["laiMax"] / p["sla"], LEAF_HARVEST_SMOOTHING, LEAF_HARVEST_MOST)


def _absorbed_par(par_gh: float, lai: float, p: Mapping[str, float]) -> float:
    """Eq 9.17 to 9.19: the PAR the canopy absorbs, from above and reflected
    from the floor (µmol m⁻² s⁻¹)."""
    entering = par_gh * (1 - p["rhoCanPar"])
    from_above = entering * (1 - math.exp(-p["k1Par"] * lai))
    from_floor = (
        p["rhoFlrPar"] * entering * math.exp(-p["k1Par"] * lai) * (1 - math.exp(-p["k2Par"] * lai))
    )
    return from_above + from_floor


def _gross_assimilation(
    t_can: float, par_can: float, co2_ppm: float, lai: float, p: Mapping[str, float]
) -> float:
    """Eq 9.12 to 9.23: photosynthesis less photorespiration (µmol CO₂ m⁻²
    s⁻¹)."""
    t_k = t_can + KELVIN_AT_0_C
    r = PER_KMOL * p["R"]
    t25 = p["t25k"]
    j25_canopy = lai * p["j25LeafMax"]
    j_potential = (
        j25_canopy
        * math.exp(p["eJ"] * (t_k - t25) / (r * t_k * t25))
        * (1 + math.exp((p["S"] * t25 - p["H"]) / (r * t25)))
        / (1 + math.exp((p["S"] * t_k - p["H"]) / (r * t_k)))
    )
    light = p["alpha"] * par_can
    theta = p["theta"]
    j = (1 / (2 * theta)) * (
        j_potential
        + light
        - math.sqrt((j_potential + light) ** 2 - 4 * theta * j_potential * light)
    )
    co2_stomata = p["etaCo2AirStom"] * co2_ppm
    leaf_share = p["j25LeafMax"] / j25_canopy
    gamma = leaf_share * p["cGamma"] * t_can + GAMMA_REFERENCE_C * p["cGamma"] * (1 - leaf_share)
    gross = j * (co2_stomata - gamma) / (ELECTRONS_PER_CO2 * (co2_stomata + 2 * gamma))
    return gross - gross * gamma / co2_stomata


def derivatives(
    state: Sequence[float], t_can: float, par_gh: float, co2_ppm: float, p: Mapping[str, float]
) -> list[float]:
    """The six states' rates of change (per s), in `STATES`' order."""
    c_buf, c_fruit, c_leaf, c_stem, t_can_sum, t_can_24 = state
    lai = leaf_area_index(c_leaf, p)

    filling = _logistic(-BUFFER_FULL_STEEPNESS, c_buf - p["cBufMax"])
    assimilated = (
        p["mCh2o"]
        * filling
        * _gross_assimilation(t_can, _absorbed_par(par_gh, lai, p), co2_ppm, lai, p)
    )

    drawing = _logistic(BUFFER_EMPTY_STEEPNESS, c_buf - p["cBufMin"])
    instant = _logistic(TCAN_LOW_STEEPNESS, t_can - p["tCanMin"]) * _logistic(
        -TCAN_HIGH_STEEPNESS, t_can - p["tCanMax"]
    )
    last_day = _logistic(TCAN24_LOW_STEEPNESS, t_can_24 - p["tCan24Min"]) * _logistic(
        -TCAN24_HIGH_STEEPNESS, t_can_24 - p["tCan24Max"]
    )
    started = t_can_sum / p["tEndSum"]
    past_end = (t_can_sum - p["tEndSum"]) / p["tEndSum"]
    generative = 0.5 * (started + math.sqrt(started**2 + TCANSUM_SMOOTHING)) - 0.5 * (
        past_end + math.sqrt(past_end**2 + TCANSUM_SMOOTHING)
    )
    growth = GROWTH_PER_C * t_can_24 + GROWTH_AT_0_C
    to_fruit = drawing * instant * last_day * generative * growth * p["rgFruit"]
    to_leaf = drawing * last_day * growth * p["rgLeaf"]
    to_stem = drawing * last_day * growth * p["rgStem"]
    growth_respiration = p["cLeafG"] * to_leaf + p["cStemG"] * to_stem + p["cFruitG"] * to_fruit

    maintenance = (1 - math.exp(-p["cRgr"] * p["rgr"])) * p["q10m"] ** (
        Q10_PER_C * (t_can_24 - Q10_REFERENCE_C)
    )
    return [
        assimilated - to_fruit - to_leaf - to_stem - growth_respiration,
        to_fruit - maintenance * c_fruit * p["cFruitM"] - fruit_harvest(c_fruit, p),
        to_leaf - maintenance * c_leaf * p["cLeafM"] - _leaf_harvest(c_leaf, p),
        to_stem - maintenance * c_stem * p["cStemM"],
        t_can / DAY_S,
        (t_can - t_can_24) / DAY_S,
    ]


@dataclass(frozen=True)
class Outputs:
    """The outputs at the hourly grid's moments (s): each state, the leaf
    area index, and the fruit's harvest rate (mg CH₂O m⁻² s⁻¹)."""

    times: list[float]
    states: dict[str, list[float]]
    lai: list[float]
    fruit_harvest: list[float]


def run(
    drivers: Drivers,
    initial: Mapping[str, float],
    p: Mapping[str, float],
    *,
    end_s: float,
    output_step_s: float,
    solver: Solver,
) -> Outputs:
    """Solves the states from 0 to `end_s` and gives the outputs every
    `output_step_s` from 0, the end left out, each interpolated linearly
    between the solver's own steps."""

    def rates(t: float, y: np.ndarray) -> list[float]:
        return derivatives([float(each) for each in y], *drivers.at(t), p)

    solution = solve_ivp(
        rates,
        (0.0, end_s),
        [initial[name] for name in STATES],
        method=solver.method,
        max_step=solver.max_step,
        atol=solver.atol,
        rtol=solver.rtol,
    )
    if not solution.success:
        raise RuntimeError(f"the solver failed: {solution.message}")
    steps = solution.t
    grid = np.arange(steps[0], steps[-1], output_step_s)
    lai = [leaf_area_index(c_leaf, p) for c_leaf in solution.y[STATES.index("cLeaf")]]
    harvest = [fruit_harvest(c_fruit, p) for c_fruit in solution.y[STATES.index("cFruit")]]
    return Outputs(
        times=[float(each) for each in grid],
        states={
            name: np.interp(grid, steps, solution.y[index]).tolist()
            for index, name in enumerate(STATES)
        },
        lai=np.interp(grid, steps, lai).tolist(),
        fruit_harvest=np.interp(grid, steps, harvest).tolist(),
    )
