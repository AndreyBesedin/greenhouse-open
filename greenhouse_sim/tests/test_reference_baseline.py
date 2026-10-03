"""Pins every reference scenario, run end to end, as the simulator behaves today.

`test_run_characterization.py` pins one small run in detail. This pins each
registered scenario as a caller would run it: every plant the scenario
describes, for its whole duration, under a fixed schedule of actions that
reaches every action type and every refusal. Each simulated day is reduced
to four digests (hidden state, observations, ground truth and action
outcomes) and each run to a readable summary of where it ended.

A failure names the scenario, the first day that diverged and which of the
four parts moved, so a restructuring that is meant to preserve behaviour
shows exactly where it did not.

The hidden-state digest covers what the world is: sizes, stages, water,
harvest. It leaves out the random draws the simple model makes when it
creates a plant or a fruit (growth multipliers, target diameters, ripening
days), so moving those draws into model-specific state changes nothing here
unless their effect on the world changes.

Floats are rounded to six decimal places before hashing, so last-bit
differences between platforms' maths libraries are not mistaken for
behaviour.

The recorded values are a snapshot of current behaviour, not a
specification. When a deliberate change moves them, regenerate the fixture
from `greenhouse_sim/`:

    python tests/test_reference_baseline.py --update

and say why in the commit message.
"""

import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from functools import cache
from pathlib import Path
from statistics import fmean

import pytest
from greenhouse_protocol.action import (
    ActionResult,
    HarvestPlantAction,
    LowerPlantAction,
    RequestedAction,
    ScheduleInspectionAction,
    WaterPlantAction,
)
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.evaluation.observation_accuracy import observation_accuracy
from greenhouse_sim.ground_truth import GroundTruth, ground_truth
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import FruitStatus, GreenhouseWorld

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "reference_baseline.json"
SCENARIOS = sorted(SCENARIO_REGISTRY)
SIMULATION_ID = "sim_reference_baseline"
DECIMALS = 6
PARTS = ("state", "observations", "ground_truth", "actions")

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


@dataclass(frozen=True)
class Baseline:
    days: list[str]
    summary: dict[str, Json]


def _schedule(day: int, plant_ids: list[str]) -> list[RequestedAction]:
    """A fixed schedule that reaches every action type and every refusal.

    It depends only on the day and each plant's position, never on the
    hidden world, so it cannot mask a behaviour change by adapting to it.
    """
    actions: list[RequestedAction] = []
    if day == 2:
        actions += [
            WaterPlantAction(plant_id="no_such_plant", amount_ml=100.0),
            WaterPlantAction(plant_id=plant_ids[0], amount_ml=0.0),
            LowerPlantAction(plant_id=plant_ids[0], amount_cm=10_000.0),
            ScheduleInspectionAction(plant_id=plant_ids[0], reason="   "),
        ]
    if day % 3 == 0:
        actions += [WaterPlantAction(plant_id=p, amount_ml=450.0) for p in plant_ids[::2]]
    if day % 4 == 0:
        actions += [HarvestPlantAction(plant_id=p) for p in plant_ids]
    if day % 5 == 0:
        actions += [LowerPlantAction(plant_id=p, amount_cm=10.0) for p in plant_ids[::3]]
    if day % 7 == 0:
        actions.append(ScheduleInspectionAction(plant_id=plant_ids[0], reason="baseline check"))
    return actions


@cache
def _run(scenario_id: str) -> Baseline:
    config = SCENARIO_REGISTRY[scenario_id]
    engine = SimulationEngine(config)
    plant_count = config.rows * config.columns
    plant_ids = [f"{scenario_id}_plant_{i:03d}" for i in range(1, plant_count + 1)]
    world = engine.initialize(plant_ids, greenhouse_id=scenario_id)
    start = datetime.combine(config.start_date, time(12, 0), tzinfo=UTC)

    days: list[str] = []
    observations: list[Observation] = []
    truths: list[GroundTruth] = []
    results: list[ActionResult] = []
    events: list[Event] = []

    for day in range(1, config.duration_days + 1):
        timestamp = start + timedelta(days=day - 1)
        step = engine.advance(world, day=day, timestamp=timestamp, simulation_id=SIMULATION_ID)
        truth = ground_truth(
            step.world, timestamp=timestamp, water_capacity_ml=config.water_capacity_ml
        )
        execution = engine.apply_actions(
            step.world, _schedule(day, plant_ids), day=day, timestamp=timestamp
        )
        world = execution.world

        parts: dict[str, Json] = {
            "state": _state(world),
            "observations": [o.model_dump(mode="json") for o in step.observations],
            "ground_truth": truth.model_dump(mode="json"),
            "actions": {
                "results": [r.model_dump(mode="json") for r in execution.results],
                "events": [e.model_dump(mode="json") for e in execution.events],
            },
        }
        digests = " ".join(f"{name}={_digest(parts[name])}" for name in PARTS)
        days.append(f"day {day:02d}: {digests}")

        observations.extend(step.observations)
        truths.append(truth)
        results.extend(execution.results)
        events.extend(execution.events)

    return Baseline(days, _summary(world, observations, truths, results, events))


def _state(world: GreenhouseWorld) -> Json:
    """The hidden world, without the simple model's creation-time draws."""
    return {
        "simulated_day": world.simulated_day,
        "environment": world.environment.model_dump(mode="json"),
        "plants": [
            {
                "plant_id": plant.plant_id,
                "age_days": plant.age_days,
                "stem_length_cm": plant.stem_length_cm,
                "lowered_length_cm": plant.lowered_length_cm,
                "water_reservoir_ml": plant.water_reservoir_ml,
                "water_stress": plant.water_stress,
                "cumulative_harvest_g": plant.cumulative_harvest_g,
                "trusses": [
                    {
                        "truss_id": truss.truss_id,
                        "index": truss.index,
                        "age_days": truss.age_days,
                        "stage": truss.stage.value,
                        "fruits": [
                            {
                                "fruit_id": fruit.fruit_id,
                                "age_days": fruit.age_days,
                                "diameter_mm": fruit.diameter_mm,
                                "mass_g": fruit.mass_g,
                                "ripeness_stage": fruit.ripeness_stage.value,
                                "status": fruit.status.value,
                            }
                            for fruit in truss.fruits
                        ],
                    }
                    for truss in plant.trusses
                ],
            }
            for plant in world.plants
        ],
    }


def _summary(
    world: GreenhouseWorld,
    observations: list[Observation],
    truths: list[GroundTruth],
    results: list[ActionResult],
    events: list[Event],
) -> dict[str, Json]:
    """Where a run ended, in numbers a reviewer can read in a diff."""
    fruits = [fruit for plant in world.plants for truss in plant.trusses for fruit in truss.fruits]
    on_plants = [fruit for fruit in fruits if fruit.status != FruitStatus.HARVESTED]
    stems = [plant.stem_length_cm for plant in world.plants]
    values_by_type: dict[str, list[float]] = {}
    for observation in observations:
        values_by_type.setdefault(observation.observation_type.value, []).append(observation.value)
    accuracy = observation_accuracy(observations, truths)

    return {
        "plants": len(world.plants),
        "days": world.simulated_day,
        "air_temperature_c": round(world.environment.air_temperature_c, 3),
        "humidity_pct": round(world.environment.humidity_pct, 3),
        "stem_length_cm": {
            "min": round(min(stems), 2),
            "mean": round(fmean(stems), 2),
            "max": round(max(stems), 2),
        },
        "lowered_length_cm": round(sum(p.lowered_length_cm for p in world.plants), 2),
        "water_reservoir_ml_mean": round(fmean(p.water_reservoir_ml for p in world.plants), 2),
        "fully_water_stressed_plants": sum(p.water_stress == 1.0 for p in world.plants),
        "trusses": sum(len(plant.trusses) for plant in world.plants),
        "fruits_by_status": _counts(fruit.status.value for fruit in fruits),
        "fruits_by_ripeness": _counts(fruit.ripeness_stage.value for fruit in fruits),
        "fruit_mass_on_plants_g": round(sum(fruit.mass_g for fruit in on_plants), 2),
        "cumulative_harvest_g": round(sum(p.cumulative_harvest_g for p in world.plants), 2),
        "actions": _counts("accepted" if r.accepted else "refused" for r in results),
        "events_by_type": _counts(event.event_type.value for event in events),
        "observations_by_type": {k: len(v) for k, v in sorted(values_by_type.items())},
        "observation_value_sums": {k: round(sum(v), 1) for k, v in sorted(values_by_type.items())},
        "observation_mean_absolute_error": {
            entry.observation_type.value: round(entry.mean_absolute_error, 3)
            for entry in accuracy.by_type
        },
    }


def _counts(values: Iterable[str]) -> dict[str, Json]:
    return {value: count for value, count in sorted(Counter(values).items())}


def _digest(value: Json) -> str:
    canonical = json.dumps(_rounded(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _rounded(value: Json) -> Json:
    if isinstance(value, float):
        return round(value, DECIMALS)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def _recorded() -> dict[str, dict[str, Json]]:
    recorded: dict[str, dict[str, Json]] = json.loads(FIXTURE.read_text())
    return recorded


def _first_divergence(actual: list[str], recorded: list[str]) -> str | None:
    for actual_day, recorded_day in zip(actual, recorded, strict=False):
        if actual_day == recorded_day:
            continue
        moved = [
            part.split("=")[0]
            for part, was in zip(actual_day.split()[2:], recorded_day.split()[2:], strict=True)
            if part != was
        ]
        return f"{actual_day.split(':')[0]} is the first to diverge, in: {', '.join(moved)}"
    if len(actual) != len(recorded):
        return f"the run lasted {len(actual)} days, not the recorded {len(recorded)}"
    return None


def test_every_registered_scenario_has_a_recorded_baseline() -> None:
    assert sorted(_recorded()) == SCENARIOS


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_a_reference_scenario_runs_day_by_day_as_recorded(scenario_id: str) -> None:
    recorded = _recorded()[scenario_id]["days"]
    assert isinstance(recorded, list)

    divergence = _first_divergence(_run(scenario_id).days, [str(day) for day in recorded])

    assert divergence is None, f"{scenario_id}: {divergence}"


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_a_reference_scenario_ends_where_recorded(scenario_id: str) -> None:
    assert _run(scenario_id).summary == _recorded()[scenario_id]["summary"]


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_the_schedule_reaches_every_action_path(scenario_id: str) -> None:
    """Otherwise the baseline would silently stop protecting an action."""
    summary = _run(scenario_id).summary
    events, actions = summary["events_by_type"], summary["actions"]
    assert isinstance(events, dict) and isinstance(actions, dict)

    assert sorted(events) == ["HARVEST", "LOWERING", "MANUAL_INSPECTION", "WATERING"]
    # The four deliberate refusals on day 2, plus any the world itself causes.
    assert isinstance(actions["refused"], int) and actions["refused"] >= 4


def _update() -> None:
    recorded = {
        scenario_id: {"summary": _run(scenario_id).summary, "days": _run(scenario_id).days}
        for scenario_id in SCENARIOS
    }
    FIXTURE.parent.mkdir(exist_ok=True)
    FIXTURE.write_text(json.dumps(recorded, indent=2) + "\n")


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_reference_baseline.py --update")
    _update()
    print(f"wrote {FIXTURE}")
