from datetime import date

from greenhouse_sim.airflow.prescribed import BuoyancyAirflow
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.world.envelope import Envelope, Opening
from greenhouse_sim.world.geometry import Point2

# The reference scenario (P05.0): a production compartment for high-wire
# tomato, the scale and shape the simulator's later projects are about.
SPANS = 4
_VENT_LENGTH_M = 6.0
_VENT_HEIGHT_M = 1.0
_DOOR_SIDE_M = 3.0

TOMATO_COMPARTMENT = ScenarioConfig(
    greenhouse_id="tomato_compartment",
    name="Tomato compartment",
    description=(
        "Reference scenario: a 24 by 16 m Venlo-style compartment of 320 high-wire "
        "tomato plants in eight rows, 28 days"
    ),
    variety="cherry_tomato",
    rows=8,
    columns=40,
    start_date=date(2026, 1, 1),
    duration_days=28,
    random_seed=2401,
    # Six 4 m bays and four 4 m spans, 6 m to the gutters: a Venlo-style
    # roof. A vent near each span's ridge, along the middle of the house,
    # stands a fifth open; a sliding door in the front gable lets trolleys
    # in, shut.
    envelope=Envelope(
        length=24.0,
        width=16.0,
        eave_height=6.0,
        ridge_height=6.8,
        spans=SPANS,
        bays=6,
        openings=[
            *(
                Opening(
                    opening_id=f"roof_vent_{span}",
                    kind=OpeningKind.ROOF_VENT,
                    surface_id=f"roof_{span}_right",
                    centre=Point2(x=0.0, y=0.5),
                    width=_VENT_LENGTH_M,
                    height=_VENT_HEIGHT_M,
                    opening=0.2,
                )
                for span in range(1, SPANS + 1)
            ),
            Opening(
                opening_id="door_front",
                kind=OpeningKind.DOOR,
                surface_id="end_wall_front",
                centre=Point2(x=8.0, y=_DOOR_SIDE_M / 2),
                width=_DOOR_SIDE_M,
                height=_DOOR_SIDE_M,
            ),
        ],
    ),
    # Its layout (scenarios/layouts/tomato_compartment/default.json): eight
    # rows along the house, 1.6 m apart, of 40 plants at 0.5 m, on hanging
    # gutters under crop wires 4 m up, with a pipe rail in each path between
    # them. A main path runs across the front, past the door, and a side path
    # along each side wall, by its heating pipes; the back is kept for
    # service, with an irrigation unit that robots keep out of. Its other
    # layout, propagation.json, raises the same rows on benches.
    layout=load_layout("tomato_compartment"),
    # Convection: two rolls across the house, rising up its middle.
    airflow=BuoyancyAirflow(),
)
