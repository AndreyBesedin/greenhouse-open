from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.config import ScenarioConfig

# Every packaged scenario, read from its manifest (`scenarios/manifests/`),
# as `catalogue.PACKAGED` holds it.
SCENARIO_REGISTRY: dict[str, ScenarioConfig] = dict(PACKAGED.configs)

__all__ = ["ScenarioConfig", "SCENARIO_REGISTRY"]
