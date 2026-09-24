"""Consume a simulation's observations through the canonical contracts.

    python examples/02_store_and_query.py

A consumer never needs to know which producer wrote a record. It stores
observations through `ObservationStore`, reads them back through
`ObservationQuery`, and asks for them only up to the instant it is deciding
at, so it cannot see the future. The in-memory store here is the reference
implementation; a database-backed one satisfies the same contracts.
"""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.contracts.canonical_store import ObservationQuery, ObservationStore
from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.contracts.memory import InMemoryObservations
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

SCENARIO = SCENARIO_REGISTRY["gh_001"]  # 40 plants
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def main() -> None:
    engine = SimulationEngine(SCENARIO)
    plant_ids = [f"{SCENARIO.greenhouse_id}_plant_{i:03d}" for i in range(1, 5)]
    world = engine.initialize(plant_ids, greenhouse_id=SCENARIO.greenhouse_id)

    records = InMemoryObservations()
    store: ObservationStore = records
    for day in range(1, 8):
        step = engine.advance(
            world, day=day, timestamp=START + timedelta(days=day - 1), simulation_id="example"
        )
        world = step.world
        # A producer can check its own output against the contract.
        violations = check_observations(step.observations)
        assert not violations, violations
        store.save_many(step.observations)

    query: ObservationQuery = records
    everything = query.list_for_greenhouse(SCENARIO.greenhouse_id)
    decided_at = START + timedelta(days=2)
    known_then = query.list_for_greenhouse(SCENARIO.greenhouse_id, up_to=decided_at)
    one_plant = query.list_for_greenhouse(SCENARIO.greenhouse_id, plant_id=plant_ids[0])

    print(f"stored {len(everything)} observations over 7 days")
    print(f"known at {decided_at.date()}: {len(known_then)} - nothing from later days")
    print(f"for {plant_ids[0]}: {len(one_plant)}")
    assert all(o.timestamp <= decided_at for o in known_then)


if __name__ == "__main__":
    main()
