from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.manifest_files import load_manifest, manifest_ids

# Every scenario, read from its manifest (`scenarios/manifests/`).
SCENARIO_REGISTRY: dict[str, ScenarioConfig] = {
    scenario_id: load_manifest(scenario_id) for scenario_id in manifest_ids()
}

__all__ = ["ScenarioConfig", "SCENARIO_REGISTRY"]
