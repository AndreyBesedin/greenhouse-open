from greenhouse_sim.scenarios.airflow_box import AIRFLOW_BOX
from greenhouse_sim.scenarios.climate_box import CLIMATE_BOX
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.greenhouse_001 import GREENHOUSE_001
from greenhouse_sim.scenarios.greenhouse_002 import GREENHOUSE_002
from greenhouse_sim.scenarios.greenhouse_demo import GREENHOUSE_DEMO
from greenhouse_sim.scenarios.tomato_compartment import TOMATO_COMPARTMENT

SCENARIO_REGISTRY: dict[str, ScenarioConfig] = {
    GREENHOUSE_001.greenhouse_id: GREENHOUSE_001,
    GREENHOUSE_002.greenhouse_id: GREENHOUSE_002,
    GREENHOUSE_DEMO.greenhouse_id: GREENHOUSE_DEMO,
    AIRFLOW_BOX.greenhouse_id: AIRFLOW_BOX,
    TOMATO_COMPARTMENT.greenhouse_id: TOMATO_COMPARTMENT,
    CLIMATE_BOX.greenhouse_id: CLIMATE_BOX,
}

__all__ = ["ScenarioConfig", "SCENARIO_REGISTRY"]
