"""What a scenario's own run's crop delivers as records (P10.4): the
harvests its crop work makes, as events, and a daily walk through the crop,
as observations, each plant's fruit counted and its height measured as a
grower would, with the scenario's own observation errors. Each of the run's
own crop actions done makes an event of its own, which names it (P13.5).

The crop is the run's crop (`scenario_crop`), of the model its rows grow,
the one the viewer draws: a harvest round picks every ripe fruit at the
start of its day, and the viewer draws the day's crop after it. The walk is
at noon, and measures each plant as its model has it:

- **the organ crop:** the fruits attached, the red ones and their mass, and
  how high its top stands; its harvest round picks fruit by fruit, which
  each plant's history keeps, with its fresh mass;
- **the simple crop** (P14.3): the fruits not harvested, the ripe ones and
  their mass, and how tall its stem stands; its harvest round picks every
  ripe fruit at once, which adds their mass to its plant's harvest.

The run's own crop actions are the organ crop's: the simple crop is given
none (`runs.crop_moment_refusal`).

A crop grown by area has no plants to walk among, nor their harvests. What
is measured of it is its measurement model's (decision 0062), which a
scenario chooses: with the part's default, the walk, nothing is; with a
canopy sample (`CanopySample`), each scope is read at the walk's moment on
the days it samples, each reading naming its scope, per m² of its floor.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from greenhouse_protocol.actions import ActionKind, Harvest, Inspect, Lower, RemoveLeaf
from greenhouse_protocol.assignment import Assignment
from greenhouse_protocol.enums import EventSource, EventType, ObservationType, SourceType
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import (
    ActionEffect,
    Harvested,
    Inspected,
    LeafRemoved,
    Lowered,
)
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.core.area_crop import AreaCrop
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.domain.scopes import AreaBasis
from greenhouse_sim.records import event_id, observation_id
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import CANOPY_SAMPLE, CanopySample, CropWalk
from greenhouse_sim.services.crop import AnyCrop, of_plants, scenario_crop
from greenhouse_sim.services.crop_models import Measured, registration
from greenhouse_sim.services.gateway import Carried
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario, with_weather
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.world.scopes import converted

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# When the day's walk through the crop is, in seconds into its day: noon.
WALK_S: Final = 12 * HOUR_S
CM_PER_M: Final = 100.0
# What a canopy sample's readings are rounded to.
SAMPLE_DECIMALS: Final = 3
# A count that a walk gets wrong is off by one, one way or the other.
MISCOUNTS: Final = (-1, 1)
# The event a crop action done makes, by its kind.
EVENT_OF: Final = {
    ActionKind.HARVEST: EventType.HARVEST,
    ActionKind.LOWER: EventType.LOWERING,
    ActionKind.REMOVE_LEAF: EventType.PRUNING,
    ActionKind.INSPECT: EventType.MANUAL_INSPECTION,
}


def crop_records(
    simulator: Simulator, run: RunRequest, day: int, start: datetime, run_id: str
) -> tuple[list[Observation], list[Event]]:
    """The harvests and the walk through the crop of a run, such as a
    scenario's own with a layout rearranged or targets changed, on its day
    `day`, which starts `day` days after `start`, each named by `run_id`."""
    config = with_weather(
        scenario(simulator.catalogue, run.scenario_id), run.weather_name(simulator.catalogue)
    )
    crop = scenario_crop(simulator, run)
    grown_by = registration(config).plants
    if grown_by is None or not of_plants(crop):
        source = RecordSource(type=SourceType.SIMULATION, source_id=run_id)
        return _sampled(config, crop, day, walk_moment(start, day), source), []
    day_start = start + timedelta(seconds=day * DAY_S)
    plants = crop.plants_on(day)
    before = crop.plants_on(day - 1) if day > 0 else plants
    # The day's crop work ends where the run's own crop actions begin.
    work = crop.worked_on(day)
    ends = {} if work is None else work.work_ends
    events = []
    for plant, earlier in zip(plants, before, strict=True):
        count, mass_g = grown_by.picked(plant, earlier, ends.get(plant.plant_id))
        if count:
            events.append(
                _harvested(plant.plant_id, day_start, config.greenhouse_id, mass_g, count)
            )
    # The walk finds the crop as the steps ended by its moment have it.
    walked_crop = crop.at(day * DAY_S + WALK_S)
    measured = [grown_by.measured(plant) for plant in walked_crop]
    walked = walk_moment(start, day)
    source = RecordSource(type=SourceType.SIMULATION, source_id=run_id)
    observations = [
        observation
        for plant in measured
        for observation in _walk(plant, config, day, walked, source)
    ]
    return observations, events


@dataclass(frozen=True)
class CropActionDone:
    """What a run made of one of its crop actions, once its day was worked
    out: as its executor reports it, by assignment, with the event it made
    if it was done."""

    assignment_id: str
    carried: Carried
    event: Event | None = None


def crop_actions_done(
    simulator: Simulator,
    run: RunRequest,
    day: int,
    start: datetime,
    assigned: Sequence[Assignment],
) -> list[CropActionDone]:
    """What a run's own crop actions at the start of its day `day`, which
    starts `day` days after `start`, did: `assigned` as its executor gives
    them, in the order the run's plan has them. Each done makes an event of
    its own, named by its assignment, and naming its action; each refused
    says why, in the organ model's words."""
    config = with_weather(
        scenario(simulator.catalogue, run.scenario_id), run.weather_name(simulator.catalogue)
    )
    work = scenario_crop(simulator, run).worked_on(day)
    worked = iter(() if work is None else work.done)
    at = start + timedelta(seconds=day * DAY_S)
    made = []
    for assignment in assigned:
        match assignment.action:
            case Inspect() as action:
                effect: ActionEffect | None = Inspected()
                refusal = None
            case Harvest() | Lower() | RemoveLeaf() as action:
                done = next(worked)
                effect, refusal = done.effect, done.refusal
            case _:
                continue
        if effect is None:
            made.append(CropActionDone(assignment.assignment_id, Carried(refusal=refusal)))
            continue
        event = Event(
            event_id=event_id(action.plant_id, at, f"{action.kind}_{assignment.assignment_id}"),
            greenhouse_id=config.greenhouse_id,
            plant_id=action.plant_id,
            timestamp=at,
            event_type=EVENT_OF[action.kind],
            source=EventSource.SIMULATION,
            parameters={**_parameters(effect, action), "action": str(assignment.ref)},
        )
        made.append(
            CropActionDone(
                assignment.assignment_id, Carried(effect=effect, event_id=event.event_id), event
            )
        )
    return made


def _parameters(effect: ActionEffect, action: CropAction | Inspect) -> dict[str, Any]:
    """What a crop action's event says it did, named as the simulator's
    other events of its kind name them (`actions.effects`)."""
    match effect:
        case Harvested(fruit_count=count, fresh_mass_g=mass):
            return {"harvested_mass_g": round(mass, 1), "harvested_fruit_count": count}
        case Lowered(by_cm=by_cm):
            return {"amount_cm": round(by_cm, 1)}
        case LeafRemoved(leaf_id=leaf_id):
            return {"leaf_id": leaf_id}
        case Inspected() if isinstance(action, Inspect):
            return {"reason": action.reason}
        case _:
            return {}


def _harvested(plant_id: str, at: datetime, greenhouse_id: str, mass_g: float, count: int) -> Event:
    return Event(
        event_id=event_id(plant_id, at, "harvest"),
        greenhouse_id=greenhouse_id,
        plant_id=plant_id,
        timestamp=at,
        event_type=EventType.HARVEST,
        source=EventSource.SIMULATION,
        # Named as the simulator's other harvests name them
        # (`actions.effects`).
        parameters={"harvested_mass_g": round(mass_g, 1), "harvested_fruit_count": count},
    )


def walk_moment(start: datetime, day: int) -> datetime:
    """When a run that starts at `start` walks its crop on its day `day`."""
    return start + timedelta(seconds=day * DAY_S + WALK_S)


# What a walk measures of each plant.
WALKED: Final = (
    ObservationType.VISIBLE_FRUIT_COUNT,
    ObservationType.RIPE_FRUIT_COUNT,
    ObservationType.ESTIMATED_RIPE_MASS_G,
    ObservationType.VISIBLE_HEIGHT_CM,
)


def walked_truly(plant: Measured) -> dict[ObservationType, float]:
    """What a walk measures of a plant, without its errors: each reading
    `_walk` records with them, for evaluation only (`greenhouse_sim.ground_truth`)."""
    return {
        ObservationType.VISIBLE_FRUIT_COUNT: float(plant.fruits),
        ObservationType.RIPE_FRUIT_COUNT: float(plant.ripe),
        ObservationType.ESTIMATED_RIPE_MASS_G: plant.ripe_mass_g,
        ObservationType.VISIBLE_HEIGHT_CM: plant.height_cm,
    }


def samples_on(config: ScenarioConfig, day: int) -> bool:
    """Whether a run of a scenario samples its canopy on its day `day`."""
    section = config.crop_walk
    return isinstance(section, CanopySample) and day % section.every_days == 0


def sampled_truly(
    config: ScenarioConfig, crop: AreaCrop[Any], day: int
) -> dict[str, dict[ObservationType, float]]:
    """What a canopy sample reads of each scope on the run's day `day`,
    without its errors, per m² of the scope's floor, by scope: for evaluation
    (`greenhouse_sim.ground_truth`), and what its readings are made from."""
    area = registration(config).area
    if area is None:
        raise ValueError(f"{config.greenhouse_id}'s crop is not grown by area")
    basis = area.rung(config).basis
    scopes = {scope.scope_id: scope for scope in crop.scopes}
    return {
        instance.scope_id: {
            kind: converted(value, scopes[instance.scope_id], basis, AreaBasis.FLOOR)
            for kind, value in area.sampled(instance.state).items()
        }
        for instance in crop.at(day * DAY_S + WALK_S)
    }


def _sampled(
    config: ScenarioConfig, crop: AnyCrop, day: int, at: datetime, source: RecordSource
) -> list[Observation]:
    """A run's canopy samples on its day `day`, if it takes any then: each
    scope's quantities, each with its own error, which no other scope's or
    day's draws change."""
    section = config.crop_walk
    if not isinstance(section, CanopySample) or of_plants(crop) or not samples_on(config, day):
        return []
    observations = []
    for scope_id, quantities in sampled_truly(config, crop, day).items():
        rng = seeded_rng(config.random_seed, CANOPY_SAMPLE, scope_id, day)
        # A scope's name is its greenhouse's own, as a plant's id is not.
        identified_by = f"{config.greenhouse_id}_{scope_id}"
        for kind, value in quantities.items():
            error_pct = section.bias_pct + rng.normal(0.0, section.noise_pct)
            observations.append(
                Observation(
                    observation_id=observation_id(identified_by, at, kind.value),
                    greenhouse_id=config.greenhouse_id,
                    plant_id=None,
                    scope_id=scope_id,
                    timestamp=at,
                    observation_type=kind,
                    value=round(max(0.0, value * (1 + error_pct / 100)), SAMPLE_DECIMALS),
                    source=source,
                )
            )
    return observations


def _walk(
    plant: Measured, config: ScenarioConfig, day: int, at: datetime, source: RecordSource
) -> Sequence[Observation]:
    """A plant as the day's walk records it: its fruits and its ripe ones
    counted, sometimes one off; the ripe ones' mass estimated; and how high
    it stands, measured; each with the scenario's own errors."""
    walk = config.crop_walk
    if not isinstance(walk, CropWalk):
        # A scenario that samples a canopy grows none of the plants walked.
        return []
    rng = seeded_rng(config.random_seed, "crop walk", plant.plant_id, day)
    estimated_g = max(
        0.0, plant.ripe_mass_g * (1 + rng.normal(0.0, walk.ripe_mass_noise_pct / 100))
    )
    measured_cm = max(0.0, plant.height_cm + rng.normal(0.0, walk.height_noise_cm))

    def observed(kind: ObservationType, value: float) -> Observation:
        return Observation(
            observation_id=observation_id(plant.plant_id, at, kind.value),
            greenhouse_id=config.greenhouse_id,
            plant_id=plant.plant_id,
            timestamp=at,
            observation_type=kind,
            value=value,
            source=source,
        )

    return [
        observed(ObservationType.VISIBLE_FRUIT_COUNT, _counted(plant.fruits, walk, rng)),
        observed(ObservationType.RIPE_FRUIT_COUNT, _counted(plant.ripe, walk, rng)),
        observed(ObservationType.ESTIMATED_RIPE_MASS_G, round(estimated_g, 1)),
        observed(ObservationType.VISIBLE_HEIGHT_CM, round(measured_cm, 1)),
    ]


def _counted(count: int, walk: CropWalk, rng: np.random.Generator) -> float:
    """A count as a walk records it: one off, either way, now and then, as a
    fruit is missed or counted twice; but none where there is none, which
    is no fruit to miscount. The draws are made either way, so that a plant
    without fruit leaves the others' counts as they were."""
    if rng.uniform() < walk.fruit_count_noise_probability:
        miscount = int(rng.choice(MISCOUNTS))
        if count > 0:
            count += miscount
    return float(count)
