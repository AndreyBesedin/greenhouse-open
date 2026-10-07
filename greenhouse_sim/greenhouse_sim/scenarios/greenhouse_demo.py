from datetime import date

from greenhouse_sim.airflow.prescribed import BuoyancyAirflow
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.world.envelope import Envelope, Opening
from greenhouse_sim.world.geometry import Point2

# Walkthrough scenario: a small greenhouse tuned so ordinary simulator
# dynamics - not scripted outcomes - reach watering, an ambiguous reading
# worth inspecting, and a harvest within about the first ten simulated days,
# instead of the ~26-40 days gh_001/gh_002 need (see the truss/ripening
# timing in greenhouse_sim/biology/tomato/simple/growth.py and ripening.py).
# A shorter greenhouse also means LOWER_PLANT is reachable in that window.
# Which policy manages it, and with what thresholds, is the caller's choice.
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
    # Room around its two rows of three plants: two 3.2 m spans, two 2 m bays,
    # a roof vent near each ridge, a side vent and a door on the back gable.
    envelope=Envelope(
        length=4.0,
        width=6.4,
        eave_height=3.0,
        ridge_height=3.65,
        spans=2,
        bays=2,
        openings=[
            *(
                Opening(
                    opening_id=f"roof_vent_{span}",
                    kind=OpeningKind.ROOF_VENT,
                    surface_id=f"roof_{span}_right",
                    centre=Point2(x=0.0, y=0.5),
                    width=1.6,
                    height=0.6,
                    opening=0.25,
                )
                for span in (1, 2)
            ),
            Opening(
                opening_id="side_vent_1",
                kind=OpeningKind.SIDE_VENT,
                surface_id="side_wall_right",
                centre=Point2(x=0.0, y=1.0),
                width=2.0,
                height=0.5,
            ),
            Opening(
                opening_id="door_1",
                kind=OpeningKind.DOOR,
                surface_id="end_wall_back",
                centre=Point2(x=1.0, y=1.05),
                width=1.2,
                height=2.1,
            ),
        ],
    ),
    # Its layout (scenarios/layouts/gh_demo/default.json): two rows of three,
    # along the length, near the front wall, grown in the soil.
    layout=load_layout("gh_demo"),
    truss_interval_days=3,
    ripening_days_bounds=(4, 7),
    # Warm air rising up the middle, sinking along the side walls.
    airflow=BuoyancyAirflow(),
)
