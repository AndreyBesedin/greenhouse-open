"""The simulator's costs on a scenario (P09.8), as its benchmark measures
them: wall-clock time per simulated day for the house's air, the plants'
light and the plants' days, worked out from the run's start; an hour of the
air cell by cell; the scene a camera's frame is drawn from, with the crop at
its fullest; and what there is to draw and to work out then. The process's
memory and the machine are the benchmark command's to say
(`greenhouse_sim.benchmark`).

Every run kept is forgotten first, so that the days measured are worked out
afresh; a state kept from a checkpoint (P09.5) is not, and a season
measured past one would carry on from it, as the API's runs do. Run it in a
process of its own.
"""

import json
import time
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import HOUSE_AIR, PLANTS_DAYS, PLANTS_LIGHT
from greenhouse_sim.core.stopwatch import Stopwatch
from greenhouse_sim.scenarios.manifest_files import manifest_digest
from greenhouse_sim.services.crop import CROPS, crop_scene, run_crop
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import CLIMATE_RUNS, field, grid
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import initial_scene, plant_ids, scenario
from greenhouse_sim.units import HOUR_S, HOURS_A_DAY, PERCENT

# The moment of the last day measured that an hour of air cell by cell is
# drawn for: noon, when the sun, the vents and the fans are all at work in
# the reference run.
NOON_S: Final = 12 * HOUR_S
MEBIBYTE: Final = 1024 * 1024
# The report's times are written to the millisecond.
REPORTED_DECIMALS: Final = 3


class DayCosts(BaseModel):
    """Seconds of wall-clock time per simulated day, on average over the
    days measured: the house's air through it, the plants' light on it, the
    plants living it with their crop work, and all three."""

    model_config = ConfigDict(frozen=True)

    house_air_s: float
    plants_light_s: float
    plants_days_s: float
    total_s: float


class DrawnCounts(BaseModel):
    """What there is to draw and to work out with the crop at its fullest:
    the scene's entities, the crop's organs and plants, and the field's
    grid, its cells along each axis and in all."""

    model_config = ConfigDict(frozen=True)

    entities: int
    organs: int
    plants: int
    field_cells: list[int]
    field_cells_total: int


class SimulatorCosts(BaseModel):
    """A scenario's run's costs, as the benchmark measured them."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    manifest_version: str
    # The days measured, from the run's start, and the time they took.
    days: int
    days_s: float
    per_day: DayCosts
    # The whole season at that rate, its every day.
    season_days: int
    season_s: float
    # An hour of the air cell by cell, drawn for a moment at noon on the
    # last day measured; and the scene a camera's frame is drawn from at
    # that day's end, the house and its crop at its fullest, and its size as
    # JSON.
    cell_by_cell_hour_s: float
    frame_scene_s: float
    frame_scene_mib: float
    counts: DrawnCounts
    # What costs the most: the next bottleneck.
    bottleneck: str


def simulator_costs(scenario_id: str, days: int | None = None) -> SimulatorCosts:
    """A scenario's run's costs, its first `days` days worked out from its
    start, by default its whole season. Only a scenario that grows its crop
    organ by organ has the plants' days to measure."""
    config = scenario(scenario_id)
    measured = config.duration_days if days is None else days
    if not 1 <= measured <= config.duration_days:
        raise InvalidRequest(
            f"{scenario_id} runs {config.duration_days} days; a benchmark measures 1 to "
            f"{config.duration_days}, not {measured}"
        )
    CLIMATE_RUNS.forget()
    CROPS.forget()
    watch = Stopwatch()
    started = time.perf_counter()
    run = RunRequest(scenario_id)
    crop = run_crop(run, watch=watch)
    plants = crop.plants_on(measured)
    days_s = time.perf_counter() - started

    noon = (measured - 1) * DAY_S + NOON_S
    started = time.perf_counter()
    field(run, "climate", time_s=noon)
    cell_by_cell_s = time.perf_counter() - started

    # The crop has lived every day measured at the last one's end.
    started = time.perf_counter()
    house = initial_scene(scenario_id)
    grown = crop_scene(run, time_s=measured * DAY_S)
    frame_s = time.perf_counter() - started
    entities = [e for e in house.entities if "organ_id" not in e.properties] + grown.entities
    frame_bytes = len(house.model_dump_json()) + len(grown.model_dump_json())

    per_day = DayCosts(
        house_air_s=watch.seconds[HOUSE_AIR] / measured,
        plants_light_s=watch.seconds[PLANTS_LIGHT] / measured,
        plants_days_s=watch.seconds[PLANTS_DAYS] / measured,
        total_s=days_s / measured,
    )
    cells = grid(scenario_id).cells
    return SimulatorCosts(
        scenario_id=scenario_id,
        manifest_version=manifest_digest(scenario_id),
        days=measured,
        days_s=days_s,
        per_day=per_day,
        season_days=config.duration_days,
        season_s=per_day.total_s * config.duration_days,
        cell_by_cell_hour_s=cell_by_cell_s,
        frame_scene_s=frame_s,
        frame_scene_mib=frame_bytes / MEBIBYTE,
        counts=DrawnCounts(
            entities=len(entities),
            organs=len({e.properties["organ_id"] for e in grown.entities}),
            plants=len(plants) or len(plant_ids(config)),
            field_cells=[cells.x, cells.y, cells.z],
            field_cells_total=cells.x * cells.y * cells.z,
        ),
        bottleneck=bottleneck(per_day, cell_by_cell_s),
    )


def bottleneck(per_day: DayCosts, cell_by_cell_hour_s: float) -> str:
    """What costs the most of a simulated day, and how the air cell by cell
    would compare were it kept through the day rather than drawn for a
    moment: the next bottleneck, in words."""
    parts = {
        "the house's air": per_day.house_air_s,
        "the plants' light": per_day.plants_light_s,
        "the plants' days": per_day.plants_days_s,
    }
    name, seconds = max(parts.items(), key=lambda part: part[1])
    share = PERCENT * seconds / per_day.total_s if per_day.total_s > 0 else 0.0
    day_of_cells = HOURS_A_DAY * cell_by_cell_hour_s
    return (
        f"{name}: {share:.0f}% of a simulated day ({seconds:.2f} s of "
        f"{per_day.total_s:.2f} s). The air cell by cell is drawn for a moment, "
        f"{cell_by_cell_hour_s:.1f} s an hour; kept through a day it would take "
        f"{day_of_cells:.0f} s, {day_of_cells / per_day.total_s:.0f} times a day "
        "of the house as one volume."
        if per_day.total_s > 0
        else f"{name}"
    )


def costs_json(costs: SimulatorCosts) -> str:
    """The costs as the report writes them, numbers rounded to milliseconds."""
    return json.dumps(_reported(costs.model_dump(mode="json")), indent=2) + "\n"


def _reported(value: object) -> object:
    if isinstance(value, float):
        return round(value, REPORTED_DECIMALS)
    if isinstance(value, dict):
        return {key: _reported(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_reported(item) for item in value]
    return value
