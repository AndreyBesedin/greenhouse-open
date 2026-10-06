from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.envelope import Envelope

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
    # Room around its four rows of ten plants: two 4.8 m spans, two 4 m bays.
    envelope=Envelope(length=8.0, width=9.6, eave_height=3.5, ridge_height=4.5, spans=2, bays=2),
)
