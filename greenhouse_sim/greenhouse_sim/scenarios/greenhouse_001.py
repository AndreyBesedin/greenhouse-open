from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.world.envelope import Envelope, Opening, OpeningKind
from greenhouse_sim.world.geometry import Point2

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
    # Room around its four rows of ten plants: two 4.8 m spans, two 4 m bays,
    # a roof vent near each ridge and a door on the front gable.
    envelope=Envelope(
        length=8.0,
        width=9.6,
        eave_height=3.5,
        ridge_height=4.5,
        spans=2,
        bays=2,
        openings=[
            *(
                Opening(
                    opening_id=f"roof_vent_{span}",
                    kind=OpeningKind.ROOF_VENT,
                    surface_id=f"roof_{span}_right",
                    centre=Point2(x=0.0, y=0.85),
                    width=3.0,
                    height=0.8,
                    opening=0.2,
                )
                for span in (1, 2)
            ),
            Opening(
                opening_id="door_1",
                kind=OpeningKind.DOOR,
                surface_id="end_wall_front",
                centre=Point2(x=1.5, y=1.05),
                width=1.2,
                height=2.1,
            ),
        ],
    ),
    # Its layout (scenarios/layouts/gh_001/default.json): four rows of ten along
    # the length, 1.6 m apart, centred in the house, each on a tomato gutter
    # under a crop wire, with a pipe rail between neighbouring rows. An aisle
    # runs across the front, past the door, and another along the right side
    # wall; heating pipes run along both side walls; the back is kept for
    # service, with an irrigation unit that robots keep out of. Its other
    # layout, benches.json, puts the same rows on benches.
    layout=load_layout("gh_001"),
)
