from datetime import date

from greenhouse_sim.airflow.prescribed import GradientAirflow
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.world.envelope import Envelope

# The sensor QA case (P06.7): the climate box's house, shut, with no
# equipment, so its air is its own and the same at every moment: still, and
# warming linearly along the house, a known truth to check sensors against.
SENSOR_LAB = ScenarioConfig(
    greenhouse_id="sensor_lab",
    name="Sensor lab",
    description=(
        "Sensor QA case: still air warming steadily along a small house, clean and "
        "imperfect thermometers side by side, and a camera looking down the house at "
        "boxes that partly hide one another"
    ),
    variety="cherry_tomato",
    rows=1,
    columns=1,
    start_date=date(2026, 1, 1),
    duration_days=10,
    random_seed=606,
    envelope=Envelope(length=12.0, width=6.4, eave_height=4.0, ridge_height=4.8, bays=3),
    # Its layout (scenarios/layouts/sensor_lab/default.json): a clean
    # thermometer 3 m along the house with an imperfect one beside it, a clean
    # one 9 m along, and a camera at the front, 1.6 m up, looking down the
    # house at three boxes on the floor, each partly hiding the one behind.
    # Its one plant stands in a front corner, behind the camera. Its second
    # layout (`blocked`) moves the nearest box in front of the camera, hiding
    # the other two.
    layout=load_layout("sensor_lab"),
    # 16 °C at the front, 0.5 °C warmer each metre: 22 °C at the back.
    airflow=GradientAirflow(front_temperature_c=16.0, rise_c_per_m=0.5),
)
