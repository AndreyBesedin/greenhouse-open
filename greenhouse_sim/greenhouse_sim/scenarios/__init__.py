from greenhouse_sim.scenarios.airflow_box import AIRFLOW_BOX
from greenhouse_sim.scenarios.climate_box import CLIMATE_BOX
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.tomato_compartment import TOMATO_COMPARTMENT

SCENARIO_REGISTRY: dict[str, ScenarioConfig] = {
    TOMATO_COMPARTMENT.greenhouse_id: TOMATO_COMPARTMENT,
    CLIMATE_BOX.greenhouse_id: CLIMATE_BOX,
    AIRFLOW_BOX.greenhouse_id: AIRFLOW_BOX,
}

__all__ = ["ScenarioConfig", "SCENARIO_REGISTRY"]
