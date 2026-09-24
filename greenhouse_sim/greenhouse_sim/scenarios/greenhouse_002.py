from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig

GREENHOUSE_002 = ScenarioConfig(
    greenhouse_id="gh_002",
    name="Longitudinal Plant Demo",
    description="Single-plant, 40-day longitudinal demo proving the config-driven architecture",
    variety="cherry_tomato",
    rows=1,
    columns=1,
    start_date=date(2026, 1, 1),
    duration_days=40,
    random_seed=2001,
)
