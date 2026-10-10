from greenhouse_sim.scenarios import SCENARIO_REGISTRY


def test_registry_contains_exactly_the_configured_greenhouses() -> None:
    assert list(SCENARIO_REGISTRY) == [
        "tomato_compartment",
        "climate_box",
        "airflow_box",
        "sensor_lab",
        "solar_lab",
    ]


def test_the_tomato_compartment_is_the_full_house_reference() -> None:
    config = SCENARIO_REGISTRY["tomato_compartment"]

    assert config.greenhouse_id == "tomato_compartment"
    assert (config.rows, config.columns) == (8, 40)
    assert config.duration_days == 28


def test_the_climate_box_is_the_small_quick_house() -> None:
    config = SCENARIO_REGISTRY["climate_box"]

    assert config.greenhouse_id == "climate_box"
    assert config.rows * config.columns == 32
    assert config.duration_days <= 15


def test_scenario_configs_have_distinct_random_seeds() -> None:
    seeds = {config.random_seed for config in SCENARIO_REGISTRY.values()}

    assert len(seeds) == len(SCENARIO_REGISTRY)


def test_a_scenario_describes_the_world_and_no_policy() -> None:
    """Which policy runs, and its thresholds, are the caller's choice about
    a run, not part of the simulated world."""
    fields = set(SCENARIO_REGISTRY["tomato_compartment"].model_dump())

    assert "management_policy" not in fields
    assert not fields & {
        "watering_trigger_reservoir_pct",
        "watering_amount_ml",
        "lower_plant_height_threshold_cm",
        "lower_plant_amount_cm",
        "harvest_ripe_fruit_count_threshold",
        "agent_tool_call_budget",
    }
