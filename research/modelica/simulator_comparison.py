"""The simulator's indoor air temperature beside TiGwerLib's, on matched
inputs, over a window of Sourisseau et al. (2026)'s season (item 6 of the
research priorities).

    python -m research.modelica.simulator_comparison FOLDER WORKDIR fig8

FOLDER is one `openmodelica setup` made. TiGwerLib's global model runs in
OpenModelica, unchanged, from its season's start to the window's end, as
`sourisseau_2026` reproduces it. The simulator runs the window in a house
built from TiGwerLib's geometry, under the weather TiGwerLib reads, its
roof vents opened as TiGwerLib's records open them and its heating giving
the heat TiGwerLib's pipes give, both read from TiGwerLib's own data. What
is compared, how the inputs are matched, what cannot be matched and the
bar a day is held to are stated in `simulator_comparison.json`, committed
before any run. The report goes to `results/simulator_<window>.json`, with
the comparison's numbers alone.
"""

import argparse
import csv
import json
import math
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

from greenhouse_sim.climate.openings import opening_sites
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.manifest_files import scenario_from_manifest
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.solar.position import sun_position
from greenhouse_sim.weather.recorded import checked_recording
from greenhouse_sim.world.site import bearing
from pydantic import JsonValue

from research.modelica import openmodelica as om
from research.modelica import sourisseau_2026 as repro
from research.modelica.sourisseau_2026 import Series, Window

HERE: Final = Path(__file__).parent
MANIFEST: Final = HERE / "simulator_comparison.json"
RESULTS: Final = HERE / "results"
# TiGwerLib's records of the CTIFL greenhouse, in the folder `setup` made.
CTIFL_DATA: Final = Path("tigwerlib/TiGwerLib/Data/CTIFL")
MAIN_DATA: Final = CTIFL_DATA / "MainData.txt"
WEATHER_DATA: Final = CTIFL_DATA / "WeatherData.txt"
# The dataset's clock: seconds from 2014-01-01 00:00 in UTC+1.
CLOCK_ZONE: Final = timezone(timedelta(hours=1))
CLOCK_ORIGIN: Final = datetime(2014, 1, 1, tzinfo=CLOCK_ZONE)
# The same zone by its IANA name, for the simulator's site.
SITE_ZONE: Final = "Etc/GMT-1"
KELVIN: Final = 273.15

# The columns of TiGwerLib's tables, counted from 1 as its tables count
# them: `WeatherData.txt`, read by the model's weather reader, and
# `MainData.txt`, its `MainDataSet`, each column y[k] its k-th.
WEATHER_TIME, WEATHER_T_C, WEATHER_RH_PCT, WEATHER_PRESSURE_PA = 1, 2, 4, 5
WEATHER_GLOBAL_W_M2, WEATHER_WIND_FROM_DEG, WEATHER_WIND_M_S = 7, 11, 12
MAIN_TIME, MAIN_LEEWARD_PCT, MAIN_WINDWARD_PCT, MAIN_T_K = 1, 5, 6, 9
# Each heating network's energy each step, in kWh per m² of floor: the
# rail pipes on the floor, the pipes in the canopy and the PE tubes.
MAIN_HEAT_KWH_M2: Final = (20, 23, 26)

# TiGwerLib's CTIFLGreenhouseBaseModel, its parameters as it gives them.
LENGTH_M: Final = 43.2
WIDTH_M: Final = 24.0
EAVE_M: Final = 6.97
RIDGE_M: Final = 7.78
# The way the greenhouse's length points, clockwise from north (its
# `spanAzimut`), the simulator's x axis.
AZIMUTH_DEG: Final = 331.0
# Its roof windows: each so long and so wide, so many per m² of floor on
# the windward and the leeward slopes, swung up to so far.
WINDOW_LENGTH_M: Final = 4.05
WINDOW_WIDTH_M: Final = 1.4
WINDWARD_PER_M2: Final = 0.021
LEEWARD_PER_M2: Final = 0.023
WINDOW_ANGLE_DEG: Final = 44.0
# Its heating: the energy each network takes in a step, filtered by this
# time constant and held below these limits, is what its pipes give the
# greenhouse (`LowPipesTotDissip`, `CanopyPipesTotDissip`,
# `PEPipesTotDissip`), from nothing at the season's start.
HEAT_TIME_CONSTANT_S: Final = 3600.0
HEAT_LIMITS_W: Final = (210_000.0, 100_000.0, 50_000.0)
# Carquefou, as its weather file's location line gives it.
LATITUDE_DEG: Final = 47.28
LONGITUDE_DEG: Final = -1.46
ELEVATION_M: Final = 29.0

# The simulator's house, where TiGwerLib gives nothing to build it from.
# Six spans: TiGwerLib's ridge and gutter heights then give its roof slope,
# 22°. Nine bays, 4.8 m apart: TiGwerLib gives none.
SPANS: Final = 6
BAYS: Final = 9
# Each orientation has as many windows as TiGwerLib's two slopes have on
# average, since either may face the wind: 23 of 4.05 m by 1.4 m, four on
# each of its first five slopes and three on its sixth, in every other bay.
WINDOW_BAYS: Final = ((1, 3, 5, 7),) * (SPANS - 1) + ((1, 4, 7),)
# A window's top edge stands this far below the ridge.
BELOW_RIDGE_M: Final = 0.01
HEATING: Final = "heating"
# What TiGwerLib's run keeps: the reproduction's air, and the heat its
# pipes give, to check the heat the simulator is given against.
PIPES: Final = ("LowPipesTotDissip", "CanopyPipesTotDissip", "PEPipesTotDissip")
KEPT: Final = repro.KEPT + r"|(LowPipes|CanopyPipes|PEPipes)TotDissip"
# The heater gives at full level what TiGwerLib's three networks give at
# most together.
HEATER_W: Final = sum(HEAT_LIMITS_W)


def manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return loaded


def read_table(path: Path) -> list[tuple[float, ...]]:
    """A table of TiGwerLib's: its rows of numbers, without its comments
    and its declaration."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = line.split()
        if not cells or cells[0].startswith("#") or cells[0].startswith("double"):
            continue
        rows.append(tuple(float(cell) for cell in cells))
    return rows


def column(rows: Iterable[Sequence[float]], index: int) -> Series:
    """One of a table's columns, counted from 1, by its moment."""
    return {round(row[0]): row[index - 1] for row in rows}


def injected_heat_w(main: Sequence[Sequence[float]], at: Window) -> Series:
    """The heat TiGwerLib's pipes give the greenhouse over each 5-minute
    step of the window, from its start, on average, in W: each network's
    energy that step, held through it as its table holds it, filtered from
    the season's start, and held below its limit, worked out exactly."""
    floor_m2 = LENGTH_M * WIDTH_M
    decay = math.exp(-om.INTERVAL_S / HEAT_TIME_CONSTANT_S)
    filtered = [0.0] * len(MAIN_HEAT_KWH_M2)
    given: Series = {}
    for row in main:
        moment = round(row[MAIN_TIME - 1])
        if moment < om.START_S or moment >= at.end_s:
            continue
        mean = 0.0
        for network, (index, limit) in enumerate(zip(MAIN_HEAT_KWH_M2, HEAT_LIMITS_W, strict=True)):
            power = 3.6e6 * floor_m2 * max(0.0, row[index - 1]) / om.INTERVAL_S
            mean += _held_below(filtered[network], power, limit)
            filtered[network] = power + (filtered[network] - power) * decay
        if moment >= at.start_s:
            given[moment] = mean
    return given


def _held_below(start_w: float, towards_w: float, limit_w: float) -> float:
    """The mean, over a step, of a first-order filter's output from
    `start_w` towards `towards_w`, held below `limit_w`."""
    tau, step = HEAT_TIME_CONSTANT_S, float(om.INTERVAL_S)

    def free_mean(start: float, span: float) -> float:
        return towards_w + (start - towards_w) * tau / span * (1.0 - math.exp(-span / tau))

    end = towards_w + (start_w - towards_w) * math.exp(-step / tau)
    if max(start_w, end) <= limit_w:
        return free_mean(start_w, step)
    if min(start_w, end) >= limit_w:
        return limit_w
    # It crosses the limit within the step: free on one side, held on the other.
    crossing = -tau * math.log((limit_w - towards_w) / (start_w - towards_w))
    if start_w < limit_w:
        return (free_mean(start_w, crossing) * crossing + limit_w * (step - crossing)) / step
    return (limit_w * crossing + free_mean(limit_w, step - crossing) * (step - crossing)) / step


def weather_recording(weather: Sequence[Sequence[float]], at: Window) -> str:
    """TiGwerLib's weather through the window, its two ends included, as the
    simulator reads a recorded weather: each record as TiGwerLib's file
    gives it, the pressure in hPa."""
    lines = [
        "timestamp,outside_air_temperature_c,outside_relative_humidity_pct,"
        "outside_barometric_pressure_hpa,outside_global_radiation_w_m2,"
        "outside_wind_speed_m_s,outside_wind_direction_deg"
    ]
    for row in weather:
        moment = round(row[WEATHER_TIME - 1])
        if not at.start_s <= moment <= at.end_s:
            continue
        lines.append(
            ",".join(
                [
                    on_the_clock(moment).isoformat(),
                    f"{row[WEATHER_T_C - 1]:g}",
                    f"{row[WEATHER_RH_PCT - 1]:g}",
                    f"{row[WEATHER_PRESSURE_PA - 1] / 100:g}",
                    f"{row[WEATHER_GLOBAL_W_M2 - 1]:g}",
                    f"{row[WEATHER_WIND_M_S - 1]:g}",
                    f"{bearing(row[WEATHER_WIND_FROM_DEG - 1]):g}",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def on_the_clock(moment_s: int) -> datetime:
    """A moment on the dataset's clock, as an instant."""
    return CLOCK_ORIGIN + timedelta(seconds=moment_s)


def ctifl_house(at: Window, recording: str, start_t_k: float, start_rh: float) -> ScenarioConfig:
    """The simulator's scenario for the window: TiGwerLib's CTIFL greenhouse
    as the simulator builds a house, its windows shut and its heater off
    until commanded, its whole house's air starting as TiGwerLib's does at
    the window's start, under the window's weather."""
    span_half_m = WIDTH_M / SPANS / 2
    slope_m = math.hypot(span_half_m, RIDGE_M - EAVE_M)
    bay_m = LENGTH_M / BAYS
    openings: list[JsonValue] = [
        {
            "opening_id": f"window_{side}_{span}_{bay}",
            "kind": "roof_vent",
            "surface_id": f"roof_{span}_{side}",
            "centre": {
                "x": (bay + 0.5) * bay_m - LENGTH_M / 2,
                "y": slope_m / 2 - WINDOW_WIDTH_M / 2 - BELOW_RIDGE_M,
            },
            "width": WINDOW_LENGTH_M,
            "height": WINDOW_WIDTH_M,
            "opening": 0.0,
            "largest_angle": math.radians(WINDOW_ANGLE_DEG),
        }
        for side in ("right", "left")
        for span, bays in enumerate(WINDOW_BAYS, start=1)
        for bay in bays
    ]
    start = on_the_clock(at.start_s)
    scenario_id = f"ctifl_{at.name}"
    document: dict[str, JsonValue] = {
        "schema_version": 7,
        "greenhouse_id": scenario_id,
        "name": f"CTIFL greenhouse, {at.name}",
        "description": "TiGwerLib's CTIFL greenhouse, for the Modelica comparison",
        "installation": {
            "installation_id": "ctifl",
            "name": "CTIFL greenhouse",
            "envelope": {
                "length": LENGTH_M,
                "width": WIDTH_M,
                "eave_height": EAVE_M,
                "ridge_height": RIDGE_M,
                "spans": SPANS,
                "bays": BAYS,
                "openings": openings,
            },
            "layout": {
                # A run grows a crop: one short row, whose plants take
                # nothing from the air.
                "crop_rows": {
                    "origin": {"x": 2.0, "y": 12.0},
                    "heading": 0.0,
                    "rows": 1,
                    "positions_per_row": 4,
                    "plant_pitch": 0.5,
                    "row_spacing": 1.6,
                },
                "equipment": [
                    {
                        "actuator_id": HEATING,
                        "heading": 0.0,
                        "base": {"x": LENGTH_M / 2, "y": WIDTH_M / 2, "z": 0.0},
                        "size_x": 1.0,
                        "size_y": 1.0,
                        "size_z": 1.0,
                        "kind": "heater",
                        "power_w": HEATER_W,
                    }
                ],
            },
            "row_crops": [{"row": 1, "crop_model": "simple", "variety": "tomato"}],
        },
        "start_date": start.date().isoformat(),
        "duration_days": (at.end_s - at.start_s) // om.DAY_S,
        "random_seed": 2015,
        "site": {
            "latitude_deg": LATITUDE_DEG,
            "longitude_deg": LONGITUDE_DEG,
            "elevation_m": ELEVATION_M,
            "time_zone": SITE_ZONE,
            "x_bearing_deg": AZIMUTH_DEG,
        },
        "models": {
            "house_air": {
                "model": "whole_house",
                "parameters": {
                    "start_temperature_c": start_t_k - KELVIN,
                    "start_humidity_pct": 100.0 * start_rh,
                },
            }
        },
    }
    config = scenario_from_manifest(scenario_id, document, layout_written=True)
    weather = checked_recording(f"ctifl_{at.name}.csv", recording.encode())
    return config.model_copy(update={"weather": weather})


def window_facing(config: ScenarioConfig) -> dict[str, float]:
    """Each of the house's windows, by the bearing its slope faces."""
    opened = config.envelope.model_copy(
        update={
            "openings": [
                opening.model_copy(update={"opening": 1.0}) for opening in config.envelope.openings
            ]
        }
    )
    return {
        opening_id: site.facing_deg
        for opening_id, site in opening_sites(opened, config.site).items()
    }


def faces_the_wind(facing_deg: float, wind_from_deg: float) -> bool:
    """Whether a slope facing `facing_deg` faces a wind from `wind_from_deg`:
    within a quarter turn of it."""
    apart = abs(bearing(wind_from_deg - facing_deg + 180.0) - 180.0)
    return apart < 90.0


def commands(
    *,
    at: Window,
    heat_w: Series,
    leeward: Series,
    windward: Series,
    wind_from_deg: Series,
    facing_deg: Mapping[str, float],
) -> list[tuple[float, str, float]]:
    """The simulator's commands through the window, on its clock: at each
    5-minute step, its heater at the share of its power TiGwerLib's pipes
    give through the step, and each window opened as TiGwerLib's records
    open the windows on its side of the roof, windward or leeward of the
    wind then; each given when it changes."""
    given: list[tuple[float, str, float]] = []
    levels: dict[str, float] = {}
    for moment in range(at.start_s, at.end_s, om.INTERVAL_S):
        wanted = {HEATING: min(heat_w[moment] / HEATER_W, 1.0)}
        for window, facing in facing_deg.items():
            side = windward if faces_the_wind(facing, wind_from_deg[moment]) else leeward
            wanted[window] = side[moment] / 100.0
        for actuator, level in wanted.items():
            if levels.get(actuator) != level:
                given.append((float(moment - at.start_s), actuator, level))
                levels[actuator] = level
    return given


def simulate(
    config: ScenarioConfig, plan: Sequence[tuple[float, str, float]], at: Window
) -> tuple[Series, dict[str, float]]:
    """The simulator's whole house through the window under `plan`: its
    air's temperature in K at every 5-minute moment, its two ends included,
    on the dataset's clock; and what the house is, as the run built it."""
    simulator = Simulator()
    simulator.catalogue.register(config)
    _, day = climate_run(
        simulator,
        RunRequest(config.greenhouse_id, plan=RunPlan.requested(commands=plan, daily=())),
    )
    house = day.house
    temperature = {}
    for moment in range(at.start_s, at.end_s + om.INTERVAL_S, om.INTERVAL_S):
        temperature[moment] = house.air_at(float(moment - at.start_s)).temperature_c + KELVIN
    end = house.air_at(float(at.end_s - at.start_s))
    glazed_m2 = sum(cells.area_m2() for cells in day.run.glazed.values())
    return temperature, {
        "air_volume_m3": house.volume_m3,
        "glazed_m2": glazed_m2,
        "heat_given_j": end.heated_j,
    }


def sun_up(config: ScenarioConfig, at: Window) -> list[int]:
    """The moments of the window, on the dataset's clock, with the sun above
    the horizon at the house's site."""
    return [
        moment
        for moment in range(at.start_s, at.end_s + om.INTERVAL_S, om.INTERVAL_S)
        if sun_position(on_the_clock(moment), config.site).is_up()
    ]


def compare(
    simulator: Series,
    tigwerlib: Series,
    measured: Series,
    *,
    sunlit: Iterable[int],
    at: Window,
    bar: float,
) -> dict[str, Any]:
    """The simulator's temperature against TiGwerLib's at every 5-minute
    moment of the window, its two ends included: the difference over the
    window, by day, and with the sun up and down; and each day's RMSE of
    both against the measurements, with whether the day's RMSE of the
    difference is within `bar`."""
    moments = range(at.start_s, at.end_s + om.INTERVAL_S, om.INTERVAL_S)
    both = [t for t in moments if t in simulator and t in tigwerlib]
    differences = {t: simulator[t] - tigwerlib[t] for t in both}
    largest = max(differences, key=lambda t: abs(differences[t]), default=None)
    lit = set(sunlit)
    days = []
    for start in range(at.start_s, at.end_s, om.DAY_S):
        day = [t for t in range(start, start + om.DAY_S, om.INTERVAL_S) if t in differences]
        rmse = _rmse(differences[t] for t in day)
        days.append(
            {
                "start_s": start,
                "compared": len(day),
                "mean_difference": _mean(differences[t] for t in day),
                "rmse_difference": rmse,
                "within_bar": rmse is not None and rmse <= bar,
                "simulator_vs_measured": _rmse(
                    simulator[t] - measured[t] for t in day if t in measured
                ),
                "tigwerlib_vs_measured": _rmse(
                    tigwerlib[t] - measured[t] for t in day if t in measured
                ),
            }
        )
    return {
        "moments": len(moments),
        "compared": len(both),
        "missing": len(moments) - len(both),
        "mean_difference": _mean(differences.values()),
        "rmse_difference": _rmse(differences.values()),
        "largest_difference": None if largest is None else differences[largest],
        "largest_at_s": largest,
        "sun_up": _part(differences, lambda t: t in lit),
        "sun_down": _part(differences, lambda t: t not in lit),
        "bar": bar,
        "days_within_bar": sum(day["within_bar"] for day in days),
        "days": days,
    }


def pipes_heat_w(results: Path) -> Series:
    """The heat TiGwerLib's pipes give, all three networks', at each moment
    of its run, as OpenModelica's CSV output writes it."""
    with results.open(encoding="utf-8", newline="") as text:
        rows = list(csv.DictReader(text))
    return {round(float(row["time"])): sum(float(row[name]) for name in PIPES) for row in rows}


def heat_check(heat_w: Series, pipes_w: Series) -> dict[str, Any]:
    """How far each step's heat, worked out here, lies from the mean of
    TiGwerLib's at the step's two ends, as its run gives it."""
    steps = [t for t in heat_w if t in pipes_w and t + om.INTERVAL_S in pipes_w]
    differences = [heat_w[t] - (pipes_w[t] + pipes_w[t + om.INTERVAL_S]) / 2 for t in steps]
    return {
        "steps": len(heat_w),
        "compared": len(steps),
        "largest_difference_w": max(map(abs, differences), default=None),
    }


def _part(differences: Mapping[int, float], keeps: Callable[[int], bool]) -> dict[str, Any]:
    kept = [d for t, d in differences.items() if keeps(t)]
    return {"compared": len(kept), "mean_difference": _mean(kept), "rmse_difference": _rmse(kept)}


def run(
    folder: Path,
    workdir: Path,
    at: Window,
    *,
    model: str = om.MODEL,
    sources: Sequence[str] = (),
) -> dict[str, Any]:
    """Runs TiGwerLib to the window's end in `workdir`, then the simulator
    through the window on the same inputs, compares them, and answers the
    report. Another model of TiGwerLib's greenhouse is run in its global
    model's place if given, from the files in `workdir` named in
    `sources`."""
    main_path, weather_path = folder / MAIN_DATA, folder / WEATHER_DATA
    for path in (main_path, weather_path):
        if not path.is_file():
            raise om.PinRefused(f"{path} is not there: run `openmodelica setup {folder}` first")
    given = manifest()
    build = om.build_global_model(
        folder,
        workdir,
        at.end_s,
        variables=KEPT,
        output_format="csv",
        model=model,
        sources=sources,
    )
    simulate_step = om.simulate_global_model(
        folder, workdir, given["tigwerlib"]["solver"], model=model
    )
    results = workdir / om.results_of(model)[1]
    tigwerlib = repro.our_series(results)
    missing_start = at.start_s not in tigwerlib["MainAir.T"]
    if missing_start or at.start_s not in tigwerlib["MainAir.RH"]:
        raise om.CheckFailed(f"TiGwerLib's results hold no air at the window's start, {at.start_s}")

    main, weather = read_table(main_path), read_table(weather_path)
    recording = weather_recording(weather, at)
    config = ctifl_house(
        at, recording, tigwerlib["MainAir.T"][at.start_s], tigwerlib["MainAir.RH"][at.start_s]
    )
    heat = injected_heat_w(main, at)
    plan = commands(
        at=at,
        heat_w=heat,
        leeward=column(main, MAIN_LEEWARD_PCT),
        windward=column(main, MAIN_WINDWARD_PCT),
        wind_from_deg=column(weather, WEATHER_WIND_FROM_DEG),
        facing_deg=window_facing(config),
    )
    began = time.monotonic()
    simulated, house = simulate(config, plan, at)
    simulator_s = time.monotonic() - began
    report = compare(
        simulated,
        tigwerlib["MainAir.T"],
        column(main, MAIN_T_K),
        sunlit=sun_up(config, at),
        at=at,
        bar=float(given["bar"]["MainAir.T"]),
    )
    tigwerlib_heat_j = sum(heat.values()) * om.INTERVAL_S
    pipes = pipes_heat_w(results)
    return {
        "window": {"name": at.name, **repro.manifest()["windows"][at.name]},
        "stated_in": last_commit(MANIFEST),
        "run": {
            "image": om.IMAGE,
            "solver": given["tigwerlib"]["solver"],
            "tolerance": om.TOLERANCE,
            "build_s": round(build.seconds),
            "simulate_s": round(simulate_step.seconds),
            "simulator": _simulator_version(),
            "simulator_s": round(simulator_s),
            "commands": len(plan),
        },
        "house": {
            "air_volume_m3": house["air_volume_m3"],
            "tigwerlib_volume_m3": LENGTH_M * WIDTH_M * (EAVE_M + (RIDGE_M - EAVE_M) / 2),
            "glazed_m2": house["glazed_m2"],
        },
        "heat": {
            "tigwerlib_j": tigwerlib_heat_j,
            "simulator_j": house["heat_given_j"],
            "against_tigwerlibs_run": heat_check(heat, pipes),
        },
        "compared": {"MainAir.T": report},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("window", choices=sorted(repro.manifest()["windows"]))
    arguments = parser.parse_args(argv)
    try:
        report = run(arguments.folder, arguments.workdir, repro.window(arguments.window))
    except (om.OpenModelicaUnavailable, om.PinRefused, om.CheckFailed) as error:
        raise SystemExit(str(error)) from error
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"simulator_{arguments.window}.json"
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    found = report["compared"]["MainAir.T"]
    sys.stdout.write(
        f"MainAir.T: RMSE of the difference {found['rmse_difference']}, mean "
        f"{found['mean_difference']}, {found['days_within_bar']} of {len(found['days'])} days "
        f"within {found['bar']}\nreport: {path}\n"
    )
    return 0


def _mean(values: Iterable[float]) -> float | None:
    given = list(values)
    return sum(given) / len(given) if given else None


def _rmse(values: Iterable[float]) -> float | None:
    given = list(values)
    return math.sqrt(sum(v * v for v in given) / len(given)) if given else None


def _simulator_version() -> str:
    """The commit the simulator runs at, marked if the files differ from it."""
    return _git(["describe", "--always", "--dirty", "--abbrev=40"])


def last_commit(path: Path) -> str:
    return _git(["log", "-1", "--format=%H", "--", str(path.relative_to(HERE))])


def _git(arguments: list[str]) -> str:
    found = subprocess.run(
        ["git", *arguments], cwd=HERE, capture_output=True, text=True, check=False
    )
    return found.stdout.strip()


if __name__ == "__main__":
    sys.exit(main())
