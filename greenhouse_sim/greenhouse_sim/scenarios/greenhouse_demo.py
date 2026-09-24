from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig

# Walkthrough scenario: a small greenhouse tuned so ordinary simulator
# dynamics - not scripted outcomes - reach watering, an ambiguous reading
# worth inspecting, and a harvest within about the first ten simulated days,
# instead of the ~26-40 days gh_001/gh_002 need (see the truss/ripening
# timing in greenhouse_sim/dynamics/growth.py and ripening.py). A shorter
# greenhouse also means LOWER_PLANT is reachable in that window. Which
# policy manages it, and with what thresholds, is the caller's choice.
GREENHOUSE_DEMO = ScenarioConfig(
    greenhouse_id="gh_demo",
    name="Agentic Demo Greenhouse",
    description=(
        "Recommended walkthrough greenhouse: 6 cherry tomato plants, 15 days, agentic "
        "management. Tuned to reach watering, inspection and harvest decisions quickly."
    ),
    variety="cherry_tomato",
    rows=2,
    columns=3,
    start_date=date(2026, 1, 1),
    duration_days=15,
    random_seed=4242,
    truss_interval_days=3,
    ripening_days_bounds=(4, 7),
)
