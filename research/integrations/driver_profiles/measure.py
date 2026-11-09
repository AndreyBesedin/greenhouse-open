"""Measures what the `house_hours` driver profile changes of each tomato
model, on a greenhouse whose canopy's temperature is known beside its air's.

    python -m research.integrations.driver_profiles.measure <forcing.csv>

The forcing is what `greenhouse.py` writes from GreenLight's greenhouse:
every 5 minutes, the air's and the canopy's temperatures, the CO₂ and the
PAR above the canopy. Each model is the package's rung, as the run grows
it, from its planted state, through the first `DAYS` whole days:

- **Vanthoor's model,** three ways:
  - `5 min, canopy`: its own drivers at their own resolution, running
    straight between the 5-minute moments, as GreenLight's crop is given
    them (four classic stages a 5 minutes, through the package's rates);
  - `hour means, canopy`: each hour's mean of them, held through the hour,
    as the profile gives an hour;
  - `hour means, air`: the same, the air's temperature for the canopy's,
    which is the profile as it is.

  The first is also set against GreenLight's own crop in the same run, to
  show that the forcing is read as GreenLight's crop reads it.
- **Reduced-State TOMGRO,** two ways: each hour's mean of the air's
  temperature, which is what its reference takes and the profile gives,
  and of the canopy's in its place.

It prints, for each comparison, each output's value at the end in both,
their difference then, and their largest difference through the season,
with its day.
"""

import csv
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from greenhouse_sim.biology.area_contract import HourDrivers, StepCourse
from greenhouse_sim.biology.tomato.tomgro.parameters import INITIAL_STATE as TOMGRO_PLANTED
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters, TomgroState
from greenhouse_sim.biology.tomato.vanthoor.growth import rates
from greenhouse_sim.biology.tomato.vanthoor.parameters import INITIAL_STATE as VANTHOOR_PLANTED
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters, VanthoorState
from greenhouse_sim.core.tomgro_crop import TomgroRung
from greenhouse_sim.core.vanthoor_crop import VanthoorRung

DAYS: Final = 109
STEP_S: Final = 300.0
STEPS_AN_HOUR: Final = 12
HOURS_A_DAY: Final = 24
CANOPY_HEIGHT_M: Final = 2.0
# GreenLight's columns of its crop's states, by the package's.
GREENLIGHT: Final = {
    "c_buf": "cBuf",
    "c_fruit": "cFruit",
    "c_leaf": "cLeaf",
    "c_stem": "cStem",
    "t_can_sum": "tCanSum",
    "t_can_24": "tCan24",
}

type Moment = dict[str, float]


def _moments(path: Path) -> list[Moment]:
    with path.open(newline="") as file:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(file)]


def _drivers(moment: Moment, temperature: str) -> HourDrivers:
    return HourDrivers(
        temperature_c=moment[temperature],
        par_above_umol_m2_s=moment["parSun"] + moment["parLamp"],
        co2_ppm=moment["co2InPpm"],
    )


def _mean(span: Sequence[Moment], key: str) -> float:
    """The mean of `key` through `span`, running straight between its
    moments: the trapezoid."""
    inner = sum(moment[key] for moment in span[1:-1])
    return (inner + (span[0][key] + span[-1][key]) / 2) / (len(span) - 1)


def _hour_means(moments: Sequence[Moment], temperature: str) -> list[HourDrivers]:
    """Each hour's mean of the drivers, `temperature` the temperature's."""
    hours = []
    for hour in range(DAYS * HOURS_A_DAY):
        span = moments[hour * STEPS_AN_HOUR : (hour + 1) * STEPS_AN_HOUR + 1]
        hours.append(
            HourDrivers(
                temperature_c=_mean(span, temperature),
                par_above_umol_m2_s=_mean(span, "parSun") + _mean(span, "parLamp"),
                co2_ppm=_mean(span, "co2InPpm"),
            )
        )
    return hours


def _between(start: HourDrivers, end: HourDrivers, share: float) -> tuple[float, float, float]:
    """The drivers `share` of the way from `start` to `end`."""
    return (
        start.temperature_c + share * (end.temperature_c - start.temperature_c),
        start.par_above_umol_m2_s + share * (end.par_above_umol_m2_s - start.par_above_umol_m2_s),
        start.co2_ppm + share * (end.co2_ppm - start.co2_ppm),
    )


def _vanthoor_by_5_minutes(moments: Sequence[Moment]) -> list[VanthoorState]:
    """Its state at each hour, its drivers running straight between the
    5-minute moments, the canopy's temperature its own."""
    p = VanthoorParameters()
    values = list(VANTHOOR_PLANTED.model_dump().values())
    season = [VANTHOOR_PLANTED]
    for step in range(DAYS * HOURS_A_DAY * STEPS_AN_HOUR):
        start, end = _drivers(moments[step], "tCan"), _drivers(moments[step + 1], "tCan")
        first, middle, last = (_between(start, end, share) for share in (0.0, 0.5, 1.0))
        h = STEP_S
        k1 = rates(values, *first, p)
        k2 = rates([v + h / 2 * r for v, r in zip(values, k1, strict=True)], *middle, p)
        k3 = rates([v + h / 2 * r for v, r in zip(values, k2, strict=True)], *middle, p)
        k4 = rates([v + h * r for v, r in zip(values, k3, strict=True)], *last, p)
        values = [
            v + h / 6 * (a + 2 * b + 2 * c + d)
            for v, a, b, c, d in zip(values, k1, k2, k3, k4, strict=True)
        ]
        if (step + 1) % STEPS_AN_HOUR == 0:
            season.append(
                VanthoorState(**dict(zip(VanthoorState.model_fields, values, strict=True)))
            )
    return season


def _vanthoor_by_hours(hours: Sequence[HourDrivers]) -> list[VanthoorState]:
    rung = VanthoorRung(VanthoorParameters(), CANOPY_HEIGHT_M)
    season = [rung.planted()]
    for hour in hours:
        season.append(rung.live_step(season[-1], StepCourse(hours=(hour,))))
    return season


def _tomgro_by_days(hours: Sequence[HourDrivers]) -> list[TomgroState]:
    rung = TomgroRung(TomgroParameters(), CANOPY_HEIGHT_M)
    season = [TOMGRO_PLANTED]
    for day in range(DAYS):
        course = StepCourse(hours=tuple(hours[day * HOURS_A_DAY : (day + 1) * HOURS_A_DAY]))
        season.append(rung.live_step(season[-1], course))
    return season


def _vanthoor_outputs(state: VanthoorState) -> dict[str, float]:
    return state.model_dump() | {"lai": state.leaf_area_index(VanthoorParameters())}


def _greenlight(moments: Sequence[Moment]) -> list[dict[str, float]]:
    """GreenLight's own crop at each hour, its leaf area index derived."""
    p = VanthoorParameters()
    kept = []
    for hour in range(DAYS * HOURS_A_DAY + 1):
        moment = moments[hour * STEPS_AN_HOUR]
        state = {field: moment[column] for field, column in GREENLIGHT.items()}
        kept.append(state | {"lai": p.sla * state["c_leaf"]})
    return kept


def _compared(
    title: str, ours: Sequence[dict[str, float]], theirs: Sequence[dict[str, float]], per_day: int
) -> None:
    """Each output both share: its value at the end in each, their
    difference then, relative to the second, and their largest difference
    through the season, with its day; `per_day` values a day."""
    print(f"\n{title}\n")
    print("| Output | At the end | Against | Difference | Largest difference | On day |")
    print("| --- | --- | --- | --- | --- | --- |")
    for name in ours[0]:
        if name not in theirs[0]:
            continue
        gaps = [abs(one[name] - other[name]) for one, other in zip(ours, theirs, strict=True)]
        largest = max(range(len(gaps)), key=gaps.__getitem__)
        end, against = ours[-1][name], theirs[-1][name]
        print(
            f"| {name} | {end:.6g} | {against:.6g} | {(end - against) / against:+.2%} | "
            f"{gaps[largest]:.3g} | {largest // per_day} |"
        )


def main(path: Path) -> None:
    moments = _moments(path)
    needed = DAYS * HOURS_A_DAY * STEPS_AN_HOUR + 1
    if len(moments) < needed or any(
        not math.isclose(moments[i]["Time"], i * STEP_S) for i in range(needed)
    ):
        raise SystemExit(f"the forcing is not {needed} moments 5 minutes apart")
    gaps = [m["tCan"] - m["tAir"] for m in moments[:needed]]
    print(
        f"The canopy's temperature less the air's, every 5 minutes: from {min(gaps):.2f} to "
        f"{max(gaps):.2f} °C, {sum(gaps) / len(gaps):.2f} on average"
    )
    canopy, air = _hour_means(moments, "tCan"), _hour_means(moments, "tAir")
    fine = [_vanthoor_outputs(s) for s in _vanthoor_by_5_minutes(moments)]
    by_canopy = [_vanthoor_outputs(s) for s in _vanthoor_by_hours(canopy)]
    by_air = [_vanthoor_outputs(s) for s in _vanthoor_by_hours(air)]
    hourly = HOURS_A_DAY
    _compared(
        "Vanthoor: 5 min, canopy, against GreenLight's crop", fine, _greenlight(moments), hourly
    )
    _compared("Vanthoor: hour means, canopy, against 5 min, canopy", by_canopy, fine, hourly)
    _compared("Vanthoor: hour means, air, against hour means, canopy", by_air, by_canopy, hourly)
    _compared(
        "Vanthoor: hour means, air (the profile), against 5 min, canopy", by_air, fine, hourly
    )
    tomgro_air = [s.model_dump() for s in _tomgro_by_days(air)]
    tomgro_canopy = [s.model_dump() for s in _tomgro_by_days(canopy)]
    _compared("TOMGRO: hour means, canopy, against hour means, air", tomgro_canopy, tomgro_air, 1)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
