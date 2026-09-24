from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig

GREENHOUSE_001 = ScenarioConfig(
    greenhouse_id="gh_001",
    name="Simulation Greenhouse 001",
    description="Primary demo greenhouse: 40 cherry tomato plants, 28 days",
    variety="cherry_tomato",
    rows=4,
    columns=10,
    start_date=date(2026, 1, 1),
    duration_days=28,
    random_seed=1001,
)
