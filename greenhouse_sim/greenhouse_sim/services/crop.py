"""A scenario's crop through a run (P09.3), as a client asks for it: the
light on each of its plants at a moment of the run, and its plants as they
stand then, drawn, grown by the model its rows grow: organ by organ
(`greenhouse_sim.core.crop`), each plant's structure, history and days
listed, or by the simple daily model (`greenhouse_sim.core.simple_crop`,
P14.3), each drawn with its numbers.

A run is asked for as its climate field is (`greenhouse_sim.services.fields`),
and refused as it is, as is a moment outside it. Its crop lives in its
climate run's house air, whether or not its layout places equipment, and
in its scenario's sunlight under its weather, its crowns as tall as its
plants stand each day. At a moment, the crop has lived the run's days that
have ended by then (`greenhouse_sim.core.clock.days_ended`).

A run's own crop actions (P13.5), its plan's harvests, lowerings and leaves
removed at the start of a day, are carried out on its crop after that
day's crop work (`RunCrop`), and refused, saying why, if the run would not
carry one out (`runs.checked_crop_plan`).

A few recent runs' crops are kept. A new one takes over the days of those
kept for the same house under the same weather, with the same doors and
vents open from the start, up to the first day their air differs on, as
its climate run takes over their air, or the day before the first their own
crop actions differ on.
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final, TypeIs

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.day import ClimateDay
from greenhouse_sim.core.clock import DAY_S, days_ended, run_day
from greenhouse_sim.core.crop import OrganRung, RunCrop
from greenhouse_sim.core.stopwatch import Stopwatch
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.services.climate_runs import RunKey, climate_run, house_of, run_label
from greenhouse_sim.services.crop_models import registration
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.kept_states import KeptState, agreeing
from greenhouse_sim.services.runs import (
    CropPlan,
    RunRequest,
    checked_crop_plan,
    checked_moment,
    crop_days,
)
from greenhouse_sim.services.scenarios import SceneChanges, changed, plant_ids, scenario
from greenhouse_sim.services.stores import Store
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.solar.plants import Crown, PlantLight
from greenhouse_sim.solar.shadows import Shadows

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# How many recent runs' crops are kept.
KEPT_CROPS: Final = 4


# What tells a run's crop from another's: its climate run, and its own crop
# actions.
type CropKey = tuple[RunKey, CropPlan]
# A run's crop, of whichever model its rows grow
# (`greenhouse_sim.services.crop_models`).
type AnyCrop = RunCrop[Any]


def crop_label(key: CropKey) -> str:
    """A kept crop's name in the log: its run's, and how many crop actions
    of its own it carries out, if any."""
    run_key, planned = key
    if not planned:
        return run_label(run_key)
    return f"{run_label(run_key)} with {len(planned)} crop actions"


def new_store() -> Store[CropKey, tuple[AnyCrop, Schedule]]:
    """A simulator's crops: the latest `KEPT_CROPS` (decision 0048)."""
    return Store("crops", KEPT_CROPS, label=crop_label)


def run_crop(
    simulator: Simulator, run: RunRequest, watch: Stopwatch | None = None
) -> RunCrop[Plant]:
    """A run's organ-level crop, as `scenario_crop` gives it; not found for
    a scenario that grows its crop with the simple daily model."""
    crop = scenario_crop(simulator, run, watch)
    if not is_organ(crop):
        raise NotFound(
            f"{run.scenario_id} grows its crop with the simple daily model, not by organ"
        )
    return crop


def is_organ(crop: AnyCrop) -> TypeIs[RunCrop[Plant]]:
    """Whether a run's crop is the organ crop."""
    return isinstance(crop.rung, OrganRung)


def scenario_crop(simulator: Simulator, run: RunRequest, watch: Stopwatch | None = None) -> AnyCrop:
    """A run's crop, grown by the model its rows grow, asked for as its
    climate field is: one of those kept, or a new one, carrying on from
    those kept for the same house up to where their air, or their own crop
    actions, differ, the parts of its days timed on `watch`, for a
    benchmark."""
    config = scenario(simulator.catalogue, run.scenario_id)
    run_key, climate = climate_run(simulator, run)
    planned = checked_crop_plan(_run_config(simulator, run_key), run.plan)
    key = (run_key, planned)
    schedule = climate.run.schedule

    def make(others: list[tuple[CropKey, tuple[AnyCrop, Schedule]]]) -> tuple[AnyCrop, Schedule]:
        crop = _new_crop(simulator, key, climate, watch)
        for (_, other_planned), (other, other_schedule) in others:
            until = schedule.same_until(other_schedule)
            shared = config.duration_days if math.isinf(until) else days_ended(until)
            alike = _worked_alike_through(planned, other_planned, config.duration_days)
            crop.carry_on_from(other, min(shared, alike, config.duration_days))
        for state in agreeing(simulator, house_of(run_key), schedule):
            if state.plants and state.crop_agrees(planned):
                crop.seed(state.day, state.plants, state.lived)
        return crop, schedule

    crop, _ = simulator.crops.made_once(key, make, lambda other: _same_house(key, other))
    return crop


def seed_kept_crops(simulator: Simulator, state: KeptState) -> None:
    """Give a kept state's plants to the crops kept that agree with it."""
    if not state.plants:
        return
    for (run_key, planned), (crop, schedule) in simulator.crops.values():
        if state.agrees(house_of(run_key), schedule) and state.crop_agrees(planned):
            crop.seed(state.day, state.plants, state.lived)


def _same_house(key: CropKey, other: CropKey) -> bool:
    """Whether two runs are of the same house, under the same weather, with
    the same doors and vents open from the start: their air is the same
    until their schedules differ, and their crops until their own crop
    actions do."""
    return house_of(key[0]) == house_of(other[0])


def _worked_alike_through(planned: CropPlan, other: CropPlan, days: int) -> int:
    """The last of a run's days on which two crops' own crop actions, and
    all of theirs before, are the same: the day before the first they
    differ on, or the run's last."""
    mine, theirs = crop_days(planned), crop_days(other)
    differing = [day for day in mine.keys() | theirs.keys() if mine.get(day) != theirs.get(day)]
    return min(differing) - 1 if differing else days


def _run_config(simulator: Simulator, key: RunKey) -> ScenarioConfig:
    """A run's scenario as its run has it: its layout, its weather and its
    doors' and vents' openings from the start."""
    scenario_id, layout, weather, _, openings, *_ = key
    return changed(
        simulator.catalogue,
        scenario(simulator.catalogue, scenario_id),
        SceneChanges(layout=layout, weather=weather, openings=dict(openings)),
    )


def _new_crop(
    simulator: Simulator, key: CropKey, climate: ClimateDay, watch: Stopwatch | None = None
) -> AnyCrop:
    """A run's crop from its first day, of the model its rows grow: the
    scenario's transplants, in its climate run's house air and its sunlight,
    its crowns grown day by day, and its own crop actions carried out; the
    parts of its days timed on `watch`, if given."""
    run_key, planned = key
    scenario_id, layout, weather, *_ = run_key
    config = _run_config(simulator, run_key)
    rung = registration(config).rung(config)
    sunlight = plant_light(simulator, scenario_id, layout, weather).sunlight

    def light(_day: int, crowns: Sequence[Crown]) -> PlantLight:
        shadows = Shadows.of(config.envelope, config.layout, [crown.solid() for crown in crowns])
        return PlantLight(sunlight.shaded_by(shadows), crowns)

    return RunCrop(
        [rung.transplant(plant_id) for plant_id in plant_ids(config)],
        config.layout.trainings(),
        config.envelope,
        rung=rung,
        air=lambda day: climate.house.mean_between(day * DAY_S, (day + 1) * DAY_S),
        light=light,
        work=config.crop_work,
        days=config.duration_days,
        planned=crop_days(planned),
        watch=watch,
    )


def crop_scene(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> SceneSnapshot:
    """A run's crop `time_s` into it, as a viewer draws it over the
    scenario's scene: each plant at its planting position, as it stands
    once it has lived the days ended by then, drawn as its model draws it
    (`CropRegistration.drawn`). Asked for as its climate field is, and
    refused as it is."""
    checked_moment(scenario(simulator.catalogue, run.scenario_id), time_s)
    crop = scenario_crop(simulator, run)
    day = days_ended(time_s)
    config = changed(
        simulator.catalogue,
        scenario(simulator.catalogue, run.scenario_id),
        SceneChanges(layout=run.layout or DEFAULT_LAYOUT),
    )
    entities = registration(config).drawn(crop.plants_on(day), config)
    return SceneSnapshot(greenhouse_id=config.greenhouse_id, simulated_day=day, entities=entities)


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
    simulator: Simulator, run: RunRequest, plant_id: str, time_s: float = 0.0
) -> CropPlant:
    """One plant of a run's crop `time_s` into it, and its days so far.
    Asked for as its crop is, and refused as it is; a plant it does not have
    is not found, nor one of the simple crop, which has no structure: its
    numbers are its entity's in the crop's scene (`crop_scene`)."""
    checked_moment(scenario(simulator.catalogue, run.scenario_id), time_s)
    crop = run_crop(simulator, run)
    day = days_ended(time_s)
    plant = next((plant for plant in crop.plants_on(day) if plant.plant_id == plant_id), None)
    if plant is None:
        raise NotFound(f"{run.scenario_id} has no plant {plant_id!r}")
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


def plants_light(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> PlantsLight:
    """The light on each of a run's plants `time_s` into it, asked for as
    its climate field is, and refused as it is: with its crowns as tall as
    its plants stand on the moment's day."""
    checked_moment(scenario(simulator.catalogue, run.scenario_id), time_s)
    day = run_day(time_s)
    crop = scenario_crop(simulator, run)
    par = crop.light_on(day).par_at(time_s)
    integrals = {plant_id: crop.local(plant_id, day).par_mol_m2_day for plant_id in par}
    try:
        return PlantsLight(
            time_s=time_s, par_umol_m2_s=par, daily_light_integral_mol_m2_d=integrals
        )
    except ValueError as unknown:
        raise InvalidRequest(str(unknown)) from unknown
