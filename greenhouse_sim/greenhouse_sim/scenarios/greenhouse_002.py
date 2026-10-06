from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Point2
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import CropRows

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
    # Its one planting position.
    layout=Layout(
        crop_rows=CropRows(
            origin=Point2(x=0.5, y=1.6),
            rows=1,
            positions_per_row=1,
            plant_pitch=0.5,
            row_spacing=1.6,
        )
    ),
)
