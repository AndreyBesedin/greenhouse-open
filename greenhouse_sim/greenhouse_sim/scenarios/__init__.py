from collections.abc import Mapping

from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.config import ScenarioConfig

# Every packaged scenario, read from its manifest (`scenarios/manifests/`),
# as `catalogue.PACKAGED` holds it: read-only, as the scenarios a simulator
# looks up are its catalogue's (decision 0048).
SCENARIO_REGISTRY: Mapping[str, ScenarioConfig] = PACKAGED.configs

__all__ = ["SCENARIO_REGISTRY", "ScenarioConfig"]
