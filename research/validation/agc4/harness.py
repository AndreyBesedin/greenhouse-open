"""Runs a tomato model on a series of AGC4 hours, as decision 0076 has it,
and reads its state per plant at every midnight.

The model is the run's own rung (`TomgroRung`, `VanthoorRung`), with the
parameters it is given, stepped through the series' hours as the run steps
it: a day at a time for Reduced-State TOMGRO, an hour at a time for
Vanthoor's model. What the harness adds is what AGC4's crop does and the
run's does not:

- **its start:** the 2023 transplants, per plant, scaled to the density at
  transplanting (`transplants`): dry weight of leaves and stem, leaf area
  and leaves. Reduced-State TOMGRO starts at as many nodes as leaves.
  Vanthoor's model takes the dry weight as its carbohydrate, one for one,
  starts its buffer where it is told, and keeps its own temperatures;
- **its spacing:** where a new density is in force, every state per m² of
  floor is multiplied by the new density over the old, so that each plant
  keeps what it had, and Reduced-State TOMGRO's ρ is the density in force.
  Vanthoor's model is spaced at the hour the density changes, which a
  summer spacing at local midnight puts at 23:00 at the days' fixed
  offset. Reduced-State TOMGRO lives a whole day to a step, so it is
  spaced at the midnight of the day its new density is in force, that
  hour later;
- **its readings:** at each midnight, per plant at the density in force:
  the fruit's dry weight (Vanthoor's standing plus harvested), the mature
  fruit's (Reduced-State TOMGRO's alone), the dry weight above ground, and
  the leaf area index, with Reduced-State TOMGRO's nodes and Vanthoor's
  leaves' and stem's dry weights.

Nothing here compares a run with a measurement: the calibration and the
test do (decision 0076).
"""

import csv
import io
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Final

import openpyxl
from greenhouse_sim.biology.area_contract import HourDrivers, StepCourse
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters, TomgroState
from greenhouse_sim.biology.tomato.vanthoor.parameters import (
    INITIAL_STATE as VANTHOOR_PUBLISHED,
)
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters, VanthoorState
from greenhouse_sim.core.tomgro_crop import TomgroRung
from greenhouse_sim.core.vanthoor_crop import VanthoorRung

from research.validation.agc4.archives import holds, members
from research.validation.agc4.drivers import HEADER, Hour

HOURS_A_DAY: Final = 24
MG_A_G: Final = 1000.0
CM2_A_M2: Final = 1e4
# Where the light above the canopy would be read in the run; the harness
# gives the rung the series' PAR, so the rung does not read this.
CANOPY_HEIGHT_M: Final = 0.5

# The pre-trial's destructive samples, and the day its transplants were
# sampled, before any treatment.
DESTRUCTIVE_WORKBOOK: Final = "DestructiveHarvest.xlsx"
DESTRUCTIVE_SHEET: Final = "All Data"
TRANSPLANTED: Final = "2023-09-04"
DATE: Final = "Date"
DRY_LEAVES: Final = "DW leaves (g/plant)"
DRY_STEM: Final = "DW stem (g/plant)"
LEAF_AREA: Final = "Leaf Area measured (cm²/plant)"
SHORT_LEAVES: Final = "N. leaves < 5 cm (#/plant)"
LONG_LEAVES: Final = "N. leaves > 5 cm (#/plant)"


@dataclass(frozen=True)
class Transplant:
    """A transplant, per plant: its leaves' and stem's dry weight (g), its
    leaf area (cm²) and its leaves."""

    dry_leaves_g: float
    dry_stem_g: float
    leaf_area_cm2: float
    leaves: float


@dataclass(frozen=True)
class Midnight:
    """A run's state at a midnight, per plant at the density in force."""

    at: datetime
    plants_per_m2: float
    fruit_dry_g: float
    dry_weight_g: float
    leaf_area_index: float
    # Reduced-State TOMGRO's alone.
    mature_fruit_dry_g: float | None = None
    nodes: float | None = None
    # Vanthoor's model's alone: Reduced-State TOMGRO does not split them.
    dry_leaves_g: float | None = None
    dry_stem_g: float | None = None


def transplants(archive: Path) -> Transplant:
    """The 2023 transplants, the mean of the plants sampled on 4 September
    2023, from the pre-trial's archive."""
    with zipfile.ZipFile(archive) as opened:
        (member,) = [n for n in members(opened) if Path(n).name == DESTRUCTIVE_WORKBOOK]
        book = openpyxl.load_workbook(io.BytesIO(opened.read(member)), data_only=True)
    rows = [r for r in book[DESTRUCTIVE_SHEET].iter_rows(values_only=True) if any(r)]
    (at,) = [i for i, row in enumerate(rows) if DATE in (str(c).strip() for c in row)]
    header = [str(cell).strip() if cell is not None else "" for cell in rows[at]]
    sampled = [row for row in rows[at + 1 :] if str(row[header.index(DATE)])[:10] == TRANSPLANTED]

    def per_plant(column: str) -> float:
        index = header.index(column)
        return mean(float(str(row[index])) for row in sampled if holds(row[index]))

    return Transplant(
        dry_leaves_g=per_plant(DRY_LEAVES),
        dry_stem_g=per_plant(DRY_STEM),
        leaf_area_cm2=per_plant(LEAF_AREA),
        leaves=per_plant(SHORT_LEAVES) + per_plant(LONG_LEAVES),
    )


def read_series(text: str) -> list[Hour]:
    """A series as `drivers.py` writes it."""
    reader = csv.reader(io.StringIO(text))
    if tuple(next(reader)) != HEADER:
        raise ValueError(f"a series' columns are {', '.join(HEADER)}")
    return [
        Hour(
            start=datetime.fromisoformat(start),
            temperature_c=float(temperature),
            par_above_umol_m2_s=float(par),
            co2_ppm=float(co2),
            plants_per_m2=float(plants),
            filled=filled == "1",
        )
        for start, temperature, par, co2, plants, filled in reader
    ]


def run_tomgro(
    parameters: TomgroParameters, transplant: Transplant, hours: Sequence[Hour]
) -> list[Midnight]:
    """Reduced-State TOMGRO through the series, a day at a time."""
    days = _days(hours)
    density = days[0][0].plants_per_m2
    state = TomgroState(
        n=transplant.leaves,
        lai=transplant.leaf_area_cm2 / CM2_A_M2 * density,
        w=(transplant.dry_leaves_g + transplant.dry_stem_g) * density,
        wf=0.0,
        wm=0.0,
    )
    midnights: list[Midnight] = []
    for day in days:
        state, density = spaced_tomgro(state, density, day[0].plants_per_m2), day[0].plants_per_m2
        midnights.append(_tomgro_midnight(day[0].start, state, density))
        rung = TomgroRung(parameters.model_copy(update={"ro": density}), CANOPY_HEIGHT_M)
        state = rung.live_step(state, StepCourse(hours=tuple(_drivers(h) for h in day)))
    end = days[-1][-1].start + (days[-1][-1].start - days[-1][-2].start)
    midnights.append(_tomgro_midnight(end, state, density))
    return midnights


def run_vanthoor(
    parameters: VanthoorParameters,
    transplant: Transplant,
    hours: Sequence[Hour],
    buffer_mg_m2: float,
) -> list[Midnight]:
    """Vanthoor's model through the series, an hour at a time, its buffer
    starting at `buffer_mg_m2` (mg CH₂O m⁻²)."""
    days = _days(hours)
    density = days[0][0].plants_per_m2
    state = VANTHOOR_PUBLISHED.model_copy(
        update={
            "c_buf": buffer_mg_m2,
            "c_fruit": 0.0,
            "c_leaf": transplant.dry_leaves_g * MG_A_G * density,
            "c_stem": transplant.dry_stem_g * MG_A_G * density,
            "harvested_fruit": 0.0,
        }
    )
    rung = VanthoorRung(parameters, CANOPY_HEIGHT_M)
    midnights: list[Midnight] = []
    for day in days:
        for hour in day:
            if hour.plants_per_m2 != density:
                state = spaced_vanthoor(state, density, hour.plants_per_m2)
                density = hour.plants_per_m2
            if hour is day[0]:
                midnights.append(_vanthoor_midnight(hour.start, state, density, parameters))
            state = rung.live_step(state, StepCourse(hours=(_drivers(hour),)))
    end = days[-1][-1].start + (days[-1][-1].start - days[-1][-2].start)
    midnights.append(_vanthoor_midnight(end, state, density, parameters))
    return midnights


def spaced_tomgro(state: TomgroState, old: float, new: float) -> TomgroState:
    """The canopy per m² once its plants stand at `new` per m², not `old`:
    each plant keeps its masses, its leaf area and its nodes."""
    ratio = new / old
    return state.model_copy(
        update={
            "lai": state.lai * ratio,
            "w": state.w * ratio,
            "wf": state.wf * ratio,
            "wm": state.wm * ratio,
        }
    )


def spaced_vanthoor(state: VanthoorState, old: float, new: float) -> VanthoorState:
    """The canopy per m² once its plants stand at `new` per m², not `old`:
    each plant keeps its carbohydrate, harvested fruit included; the
    temperatures are the canopy's, not per m²."""
    ratio = new / old
    return state.model_copy(
        update={
            "c_buf": state.c_buf * ratio,
            "c_fruit": state.c_fruit * ratio,
            "c_leaf": state.c_leaf * ratio,
            "c_stem": state.c_stem * ratio,
            "harvested_fruit": state.harvested_fruit * ratio,
        }
    )


def _tomgro_midnight(at: datetime, state: TomgroState, density: float) -> Midnight:
    return Midnight(
        at=at,
        plants_per_m2=density,
        fruit_dry_g=state.wf / density,
        dry_weight_g=state.w / density,
        leaf_area_index=state.lai,
        mature_fruit_dry_g=state.wm / density,
        nodes=state.n,
    )


def _vanthoor_midnight(
    at: datetime, state: VanthoorState, density: float, parameters: VanthoorParameters
) -> Midnight:
    # Carbohydrate is taken for dry matter, one for one (decision 0076).
    fruit = state.c_fruit + state.harvested_fruit
    above_ground = state.c_buf + state.c_leaf + state.c_stem + fruit
    return Midnight(
        at=at,
        plants_per_m2=density,
        fruit_dry_g=fruit / MG_A_G / density,
        dry_weight_g=above_ground / MG_A_G / density,
        leaf_area_index=state.leaf_area_index(parameters),
        dry_leaves_g=state.c_leaf / MG_A_G / density,
        dry_stem_g=state.c_stem / MG_A_G / density,
    )


def _days(hours: Sequence[Hour]) -> list[Sequence[Hour]]:
    if not hours or len(hours) % HOURS_A_DAY:
        raise ValueError(f"a series is whole days of {HOURS_A_DAY} hours, not {len(hours)} hours")
    return [hours[i : i + HOURS_A_DAY] for i in range(0, len(hours), HOURS_A_DAY)]


def _drivers(hour: Hour) -> HourDrivers:
    return HourDrivers(
        temperature_c=hour.temperature_c,
        par_above_umol_m2_s=hour.par_above_umol_m2_s,
        co2_ppm=hour.co2_ppm,
    )
