"""A scenario's crop through a run (P09.3), as a client asks for it: the
light on each of its plants at a moment of the run, and, where it grows
its crop organ by organ (`greenhouse_sim.core.crop`), its plants as they
stand then, drawn organ by organ, and each plant's structure, history and
days.

A run is asked for as its climate field is (`greenhouse_sim.services.fields`),
and refused as it is, as is a moment outside it. Its crop lives in its
climate run's house air, whether or not its layout places equipment, and
in its scenario's sunlight under its weather, its crowns as tall as its
plants stand each day. At a moment, the crop has lived the run's days that
have ended by then (`greenhouse_sim.core.clock.days_ended`).

A few recent runs' crops are kept. A new one takes over the days of those
kept for the same house under the same weather, with the same doors and
vents open from the start, up to the first day their air differs on, as
its climate run takes over their air.
"""

import math
import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.biology.tomato.organ.transplants import transplant
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.day import ClimateDay
from greenhouse_sim.core.clock import DAY_S, days_ended, run_day
from greenhouse_sim.core.crop import CropLight, RunCrop
from greenhouse_sim.core.stopwatch import Stopwatch
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.scene.plants import crop_entities
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.fields import Commanded, RunKey, climate_run
from greenhouse_sim.services.kept_states import House, KeptState, agreeing
from greenhouse_sim.services.making import Kept, kept_values, made_once
from greenhouse_sim.services.runs import checked_moment
from greenhouse_sim.services.scenarios import SceneChanges, changed, plant_ids, scenario
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.solar.plants import Crown, PlantLight
from greenhouse_sim.solar.shadows import Shadows

# How many recent runs' crops are kept.
KEPT_CROPS: Final = 4

_KEPT: Kept[RunKey, tuple[RunCrop, Schedule]] = OrderedDict()
_KEEPING = threading.Lock()


def forget_crops() -> None:
    """Forget the kept crops, so that the next one asked for grows afresh."""
    with _KEEPING:
        _KEPT.clear()


def run_crop(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    weather: str | None = None,
    daily: Sequence[Commanded] | None = None,
    watch: Stopwatch | None = None,
) -> RunCrop:
    """A scenario's organ-level crop through a run, asked for as its climate
    field is: one of those kept, or a new one, carrying on from those kept
    for the same house up to where their air differs, the parts of its days
    timed on `watch`, for a benchmark. A scenario that grows its crop with
    the simple daily model has none."""
    config = scenario(scenario_id)
    if config.crop_model != CropModel.ORGAN:
        raise NotFound(f"{scenario_id} grows its crop with the simple daily model, not by organ")
    key, climate = climate_run(scenario_id, layout, levels, openings, commands, weather, daily)
    schedule = climate.run.schedule

    def make(others: list[tuple[RunKey, tuple[RunCrop, Schedule]]]) -> tuple[RunCrop, Schedule]:
        crop = _new_crop(key, climate, watch)
        for _, (other, other_schedule) in others:
            until = schedule.same_until(other_schedule)
            shared = config.duration_days if math.isinf(until) else days_ended(until)
            crop.carry_on_from(other, min(shared, config.duration_days))
        for state in agreeing(_house(key), schedule):
            if state.plants:
                crop.seed(state.day, state.plants, state.lived)
        return crop, schedule

    crop, _ = made_once(
        _KEPT, _KEEPING, key, KEPT_CROPS, lambda other: _same_house(key, other), make
    )
    return crop


def seed_kept_crops(state: KeptState) -> None:
    """Give a kept state's plants to the crops kept that agree with it."""
    if not state.plants:
        return
    for key, (crop, schedule) in kept_values(_KEPT, _KEEPING):
        if state.agrees(_house(key), schedule):
            crop.seed(state.day, state.plants, state.lived)


def _house(key: RunKey) -> House:
    """A run's house, as its key names it."""
    scenario_id, layout, weather, _, openings, _ = key
    return scenario_id, layout, weather, openings


def _same_house(key: RunKey, other: RunKey) -> bool:
    """Whether two runs are of the same house, under the same weather, with
    the same doors and vents open from the start: their air is the same
    until their schedules differ."""
    return _house(key) == _house(other)


def _new_crop(key: RunKey, climate: ClimateDay, watch: Stopwatch | None = None) -> RunCrop:
    """A run's crop from its first day: the scenario's transplants, in its
    climate run's house air and its sunlight, its crowns grown day by day;
    the parts of its days timed on `watch`, if given."""
    scenario_id, layout, weather, _, openings, _ = key
    config = changed(
        scenario(scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(openings)),
    )
    sunlight = plant_light(scenario_id, layout, weather).sunlight

    def light(_day: int, crowns: Sequence[Crown]) -> PlantLight:
        shadows = Shadows.of(config.envelope, config.layout, [crown.solid() for crown in crowns])
        return PlantLight(sunlight.shaded_by(shadows), crowns)

    return RunCrop(
        [transplant(plant_id, config.random_seed) for plant_id in plant_ids(config)],
        config.layout.trainings(),
        config.envelope,
        air=lambda day: climate.house.mean_between(day * DAY_S, (day + 1) * DAY_S),
        light=light,
        work=config.crop_work,
        days=config.duration_days,
        watch=watch,
    )


def crop_scene(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    time_s: float = 0.0,
    weather: str | None = None,
    daily: Sequence[Commanded] | None = None,
) -> SceneSnapshot:
    """A scenario's crop `time_s` into a run, organ by organ, as a viewer
    draws it over the scenario's scene: each plant at its planting position,
    as it stands once it has lived the days ended by then. Asked for as its
    climate field is, and refused as it is."""
    checked_moment(scenario(scenario_id), time_s)
    crop = run_crop(scenario_id, layout, levels, openings, commands, weather, daily)
    day = days_ended(time_s)
    config = changed(scenario(scenario_id), SceneChanges(layout=layout or DEFAULT_LAYOUT))
    return SceneSnapshot(
        greenhouse_id=config.greenhouse_id,
        simulated_day=day,
        entities=crop_entities(crop.plants_on(day), config.layout.trainings(), config.envelope),
    )


class CropPlant(BaseModel):
    """One plant of a scenario's crop `time_s` into a run, once it has lived
    the run's first `days` days: its structure, organ by organ, with its
    history, and what it experienced on each of those days, from the
    first."""

    model_config = ConfigDict(frozen=True)

    time_s: float
    days: int
    structure: Plant
    environments: list[LocalEnvironment]


def crop_plant(
    scenario_id: str,
    plant_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    time_s: float = 0.0,
    weather: str | None = None,
    daily: Sequence[Commanded] | None = None,
) -> CropPlant:
    """One plant of a scenario's crop `time_s` into a run, and its days so
    far. Asked for as its crop is, and refused as it is; a plant it does not
    have is not found."""
    checked_moment(scenario(scenario_id), time_s)
    crop = run_crop(scenario_id, layout, levels, openings, commands, weather, daily)
    day = days_ended(time_s)
    plant = next((plant for plant in crop.plants_on(day) if plant.plant_id == plant_id), None)
    if plant is None:
        raise NotFound(f"{scenario_id} has no plant {plant_id!r}")
    return CropPlant(
        time_s=time_s,
        days=day,
        structure=plant,
        environments=crop.environments(plant_id, day),
    )


class PlantsLight(BaseModel):
    """The light on each of a scenario's plants at a moment of a run, in
    seconds from its start: its PAR then, in µmol/m²/s, and its daily light
    integral on the day the moment belongs to (`greenhouse_sim.core.clock`),
    in mol/m²/d, by plant."""

    model_config = ConfigDict(frozen=True)

    time_s: float
    par_umol_m2_s: dict[str, float]
    daily_light_integral_mol_m2_d: dict[str, float]


def plants_light(
    scenario_id: str,
    layout: str | None = None,
    levels: Mapping[str, float] | None = None,
    openings: Mapping[str, float] | None = None,
    commands: Sequence[Commanded] = (),
    time_s: float = 0.0,
    weather: str | None = None,
    daily: Sequence[Commanded] | None = None,
) -> PlantsLight:
    """The light on each of a scenario's plants `time_s` into a run, asked
    for as its climate field is, and refused as it is: with its crowns as
    tall as its plants stand on the moment's day, where it grows its crop
    organ by organ; or else as they stand before its first day."""
    checked_moment(scenario(scenario_id), time_s)
    key, _ = climate_run(scenario_id, layout, levels, openings, commands, weather, daily)
    day = run_day(time_s)
    light: CropLight
    if scenario(scenario_id).crop_model == CropModel.ORGAN:
        crop = run_crop(scenario_id, layout, levels, openings, commands, weather, daily)
        light = crop.light_on(day)
        par = light.par_at(time_s)
        integrals = {plant_id: crop.local(plant_id, day).par_mol_m2_day for plant_id in par}
    else:
        _, name, under, *_ = key
        light = plant_light(scenario_id, name, under)
        par = light.par_at(time_s)
        integrals = light.daily_light_integral(day)
    try:
        return PlantsLight(
            time_s=time_s, par_umol_m2_s=par, daily_light_integral_mol_m2_d=integrals
        )
    except ValueError as unknown:
        raise InvalidRequest(str(unknown)) from unknown
