from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.envelope import Envelope

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
    # A small house around its single plant.
    envelope=Envelope(length=4.0, width=3.2, eave_height=3.0, ridge_height=3.65),
)
