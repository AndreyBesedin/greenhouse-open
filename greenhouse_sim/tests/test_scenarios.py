from greenhouse_sim.scenarios import SCENARIO_REGISTRY


def test_registry_contains_exactly_the_three_configured_greenhouses() -> None:
    assert set(SCENARIO_REGISTRY) == {"gh_001", "gh_002", "gh_demo"}


def test_greenhouse_001_is_the_forty_plant_primary_scenario() -> None:
    config = SCENARIO_REGISTRY["gh_001"]

    assert config.greenhouse_id == "gh_001"
    assert config.rows * config.columns == 40
    assert config.rows == 4
    assert config.columns == 10
    assert config.duration_days == 28


def test_greenhouse_002_is_the_single_plant_longitudinal_scenario() -> None:
    config = SCENARIO_REGISTRY["gh_002"]

    assert config.greenhouse_id == "gh_002"
    assert config.rows * config.columns == 1
    assert config.duration_days == 40


def test_greenhouse_demo_is_the_short_walkthrough_scenario() -> None:
    config = SCENARIO_REGISTRY["gh_demo"]

    assert config.greenhouse_id == "gh_demo"
    assert config.duration_days <= 15


def test_scenario_configs_have_distinct_random_seeds() -> None:
    seeds = {config.random_seed for config in SCENARIO_REGISTRY.values()}

    assert len(seeds) == len(SCENARIO_REGISTRY)


def test_a_scenario_describes_the_world_and_no_policy() -> None:
    """Which policy runs, and its thresholds, are the caller's choice about
    a run, not part of the simulated world."""
    fields = set(SCENARIO_REGISTRY["gh_001"].model_dump())

    assert "management_policy" not in fields
    assert not fields & {
        "watering_trigger_reservoir_pct",
        "watering_amount_ml",
        "lower_plant_height_threshold_cm",
        "lower_plant_amount_cm",
        "harvest_ripe_fruit_count_threshold",
        "agent_tool_call_budget",
    }
