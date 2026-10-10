from datetime import date

from greenhouse_sim.airflow.prescribed import UniformAirflow
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.weather.presets import COLD_SPRING_DAY
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3

# The sun's QA case (P08): the climate box's house, shut, at the March
# equinox under a clear spring sky, so that the sun's path, the light
# through the glass and the shadows inside can be checked against values
# known for the day.
SOLAR_LAB = ScenarioConfig(
    greenhouse_id="solar_lab",
    name="Solar lab",
    description=(
        "Sun QA case: a small shut house at the March equinox under a clear sky, a row of "
        "plants partly shaded by a stack of crates, and PAR sensors in the sun and the shade"
    ),
    variety="cherry_tomato",
    rows=1,
    columns=16,
    start_date=date(2026, 3, 20),
    duration_days=10,
    random_seed=808,
    envelope=Envelope(length=12.0, width=6.4, eave_height=4.0, ridge_height=4.8, bays=3),
    # Its layout (scenarios/layouts/solar_lab/default.json): one row of 16
    # plants along the middle of the house on a crop gutter; a stack of
    # crates 1.5 m high just south of its first four plants, which shades
    # them at noon; PAR sensors 0.3 m up on either side of the crates, in
    # the sun to their south and in their shade to their north; and a heater,
    # off, in the back right corner, so that the house has a climate run.
    layout=load_layout("solar_lab"),
    airflow=UniformAirflow(velocity_m_s=Vector3(x=0.0, y=0.0, z=0.0)),
    # The cold spring day, without a cloud.
    weather=COLD_SPRING_DAY.model_copy(update={"cloud_cover_pct": 0.0}),
)
