"""What a scenario's own run's crop delivers as records (P10.4): the
harvests its crop work makes, as events, and a daily walk through the crop,
as observations, each plant's fruit counted and its height measured as a
grower would, with the scenario's own observation errors. Each of the run's
own crop actions done makes an event of its own, which names it (P13.5).

The crop is the run's organ-level crop (`run_crop`), the one the viewer
draws: a harvest round picks every red fruit at the start of its day, which
each plant's history keeps, fruit by fruit, with its fresh mass; the viewer
draws the day's crop after it. The walk is at noon. A scenario that grows its
crop with the simple daily model has no organ-level crop, and no records of
it here.
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

from greenhouse_sim.biology.plant.organs import Fruit
from greenhouse_sim.biology.tomato.organ.fruit import is_red
from greenhouse_sim.biology.tomato.organ.geometry import top_height_m
from greenhouse_sim.biology.tomato.organ.topology import HarvestFruit, Plant
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.organs import FruitStage
from greenhouse_sim.records import event_id, observation_id
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.crop import run_crop
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
    `day`, which starts `day` days after `start`, each named by `run_id`:
    none if the scenario grows no organ-level crop."""
    config = scenario(simulator.catalogue, run.scenario_id)
    if config.crop_model != CropModel.ORGAN:
        return [], []
    crop = run_crop(simulator, run)
    plants = crop.plants_on(day)
    before = crop.plants_on(day - 1) if day > 0 else plants
    day_start = start + timedelta(seconds=day * DAY_S)
    # The day's crop work ends where the run's own crop actions begin.
    work = crop.worked_on(day)
    ends = {} if work is None else work.work_ends
    events = [
        harvest
        for plant, earlier in zip(plants, before, strict=True)
        if (
            harvest := _harvest(
                plant, earlier, day_start, config.greenhouse_id, ends.get(plant.plant_id)
            )
        )
        is not None
    ]
    walked = day_start + timedelta(seconds=WALK_S)
    source = RecordSource(type=SourceType.SIMULATION, source_id=run_id)
    observations = [
        observation for plant in plants for observation in _walk(plant, config, day, walked, source)
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
    work = run_crop(simulator, run).worked_on(day)
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


def _harvest(
    plant: Plant, earlier: Plant, at: datetime, greenhouse_id: str, until: int | None = None
) -> Event | None:
    """What the day's harvest round picked from a plant, as one event: the
    fruits picked since the day before and their fresh mass, by the crop
    work alone, which ends where its history is `until` long, if given."""
    picked = [
        event
        for event in plant.history[len(earlier.history) : until]
        if event.applied and isinstance(event.action, HarvestFruit)
    ]
    if not picked:
        return None
    return Event(
        event_id=event_id(plant.plant_id, at, "harvest"),
        greenhouse_id=greenhouse_id,
        plant_id=plant.plant_id,
        timestamp=at,
        event_type=EventType.HARVEST,
        source=EventSource.SIMULATION,
        # Named as the simulator's other harvests name them
        # (`actions.effects`).
        parameters={
            "harvested_mass_g": round(sum(event.harvested_g for event in picked), 1),
            "harvested_fruit_count": len(picked),
        },
    )


def _fruits(plant: Plant) -> list[Fruit]:
    return [
        flower.fruit
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None and flower.fruit.stage == FruitStage.ATTACHED
    ]


def _walk(
    plant: Plant, config: ScenarioConfig, day: int, at: datetime, source: RecordSource
) -> Sequence[Observation]:
    """A plant as the day's walk records it: its fruits and its red ones
    counted, sometimes one off; the red ones' mass estimated; and how high
    its top stands, measured; each with the scenario's own errors."""
    rng = seeded_rng(config.random_seed, "crop walk", plant.plant_id, day)
    fruits = _fruits(plant)
    red = [fruit for fruit in fruits if is_red(fruit.ripeness)]
    red_mass_g = sum(fruit.mass_g for fruit in red)
    estimated_g = max(
        0.0, red_mass_g * (1 + rng.normal(0.0, config.crop_walk.ripe_mass_noise_pct / 100))
    )
    height_cm = top_height_m(plant) * CM_PER_M
    measured_cm = max(0.0, height_cm + rng.normal(0.0, config.crop_walk.height_noise_cm))

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
        observed(ObservationType.VISIBLE_FRUIT_COUNT, _counted(len(fruits), config, rng)),
        observed(ObservationType.RIPE_FRUIT_COUNT, _counted(len(red), config, rng)),
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
