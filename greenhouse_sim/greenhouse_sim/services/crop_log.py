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

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.records import event_id, observation_id
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.crop import of_plants, scenario_crop
from greenhouse_sim.services.crop_models import Measured, registration
from greenhouse_sim.services.gateway import Carried
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.units import HOUR_S

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# When the day's walk through the crop is, in seconds into its day: noon.
WALK_S: Final = 12 * HOUR_S
CM_PER_M: Final = 100.0
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
    config = scenario(simulator.catalogue, run.scenario_id)
    crop = scenario_crop(simulator, run)
    grown_by = registration(config).plants
    if grown_by is None or not of_plants(crop):
        # A crop grown by area has no plants to walk among, nor their
        # harvests: what is measured of it is its measurement models'.
        return [], []
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
    config = scenario(simulator.catalogue, run.scenario_id)
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


def _walk(
    plant: Measured, config: ScenarioConfig, day: int, at: datetime, source: RecordSource
) -> Sequence[Observation]:
    """A plant as the day's walk records it: its fruits and its ripe ones
    counted, sometimes one off; the ripe ones' mass estimated; and how high
    it stands, measured; each with the scenario's own errors."""
    rng = seeded_rng(config.random_seed, "crop walk", plant.plant_id, day)
    estimated_g = max(
        0.0, plant.ripe_mass_g * (1 + rng.normal(0.0, config.crop_walk.ripe_mass_noise_pct / 100))
    )
    measured_cm = max(0.0, plant.height_cm + rng.normal(0.0, config.crop_walk.height_noise_cm))

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
        observed(ObservationType.VISIBLE_FRUIT_COUNT, _counted(plant.fruits, config, rng)),
        observed(ObservationType.RIPE_FRUIT_COUNT, _counted(plant.ripe, config, rng)),
        observed(ObservationType.ESTIMATED_RIPE_MASS_G, round(estimated_g, 1)),
        observed(ObservationType.VISIBLE_HEIGHT_CM, round(measured_cm, 1)),
    ]


def _counted(count: int, config: ScenarioConfig, rng: np.random.Generator) -> float:
    """A count as a walk records it: one off, either way, now and then, as a
    fruit is missed or counted twice; but none where there is none, which
    is no fruit to miscount. The draws are made either way, so that a plant
    without fruit leaves the others' counts as they were."""
    if rng.uniform() < config.crop_walk.fruit_count_noise_probability:
        miscount = int(rng.choice(MISCOUNTS))
        if count > 0:
            count += miscount
    return float(count)
