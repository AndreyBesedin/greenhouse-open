"""The scenarios a simulator knows (decision 0048): the packaged ones, read
once and never changed, and those registered with one simulator's
catalogue, never in place of a packaged one nor of another registered."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import (
    PACKAGED,
    Catalogue,
    PackagedScenarios,
    ScenarioRefused,
    Scenarios,
    config_digest,
)
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT, layout_names
from greenhouse_sim.scenarios.manifest_files import (
    load_manifest,
    manifest_digest,
    manifest_ids,
    opening_day,
)

# How many threads register the same scenario at once.
REGISTERING = 8


def _copy_of(scenario_id: str, new_id: str, **changes: object) -> ScenarioConfig:
    """A packaged scenario under another identifier, changed as asked."""
    return SCENARIO_REGISTRY[scenario_id].model_copy(update={"greenhouse_id": new_id, **changes})


@pytest.mark.parametrize("scenario_id", manifest_ids())
def test_a_packaged_scenario_is_its_manifest(scenario_id: str) -> None:
    entry = PACKAGED.entry(scenario_id)

    assert entry is not None and entry.packaged
    assert entry.config == load_manifest(scenario_id)
    assert entry.version == manifest_digest(scenario_id)
    assert entry.opening_day == opening_day(scenario_id)
    assert entry.layouts == tuple(layout_names(scenario_id))


def test_the_packaged_scenarios_are_listed_and_kept_as_the_registry_holds_them() -> None:
    assert PACKAGED.ids() == manifest_ids()
    assert list(SCENARIO_REGISTRY) == manifest_ids()
    assert all(SCENARIO_REGISTRY[key] is config for key, config in PACKAGED.configs.items())


def test_the_packaged_scenarios_never_change() -> None:
    config = PACKAGED.configs["climate_box"]

    with pytest.raises(TypeError):
        PACKAGED.configs["climate_box"] = config  # type: ignore[index]
    with pytest.raises(ValidationError, match="frozen"):
        SCENARIO_REGISTRY["climate_box"].random_seed = 7  # type: ignore[misc]
    reseeded = PACKAGED.with_config(config.model_copy(update={"random_seed": 7}))

    assert PACKAGED.configs["climate_box"] is config
    changed = reseeded.entry("climate_box")
    assert changed is not None and changed.config.random_seed == 7
    assert changed.version == config_digest(changed.config) != manifest_digest("climate_box")
    assert reseeded.ids() == PACKAGED.ids()
    with pytest.raises(KeyError):
        PACKAGED.with_config(_copy_of("climate_box", "no_such_box"))


def test_a_registered_scenario_is_known_after_the_packaged_ones() -> None:
    catalogue = Catalogue()
    config = _copy_of("climate_box", "drafted_box")

    entry = catalogue.register(config)

    assert entry.config is config and not entry.packaged
    assert entry.version == config_digest(config)
    assert entry.opening_day is None
    assert entry.layouts == (DEFAULT_LAYOUT,)
    assert catalogue.entry("drafted_box") is entry
    assert catalogue.entry("climate_box") is PACKAGED.entry("climate_box")
    assert catalogue.ids() == [*manifest_ids(), "drafted_box"]


def test_the_same_scenario_registered_again_is_the_one_known() -> None:
    catalogue = Catalogue()
    first = catalogue.register(_copy_of("climate_box", "drafted_box"))

    again = catalogue.register(_copy_of("climate_box", "drafted_box"))

    assert again is first
    assert catalogue.ids().count("drafted_box") == 1


def test_another_scenario_under_a_registered_name_is_refused() -> None:
    catalogue = Catalogue()
    first = catalogue.register(_copy_of("climate_box", "drafted_box"))

    with pytest.raises(ScenarioRefused, match="registered as another scenario"):
        catalogue.register(_copy_of("climate_box", "drafted_box", random_seed=99))
    assert catalogue.entry("drafted_box") is first


def test_a_packaged_scenario_is_never_replaced() -> None:
    catalogue = Catalogue()

    with pytest.raises(ScenarioRefused, match="packaged"):
        catalogue.register(SCENARIO_REGISTRY["climate_box"])
    with pytest.raises(ScenarioRefused, match="packaged"):
        catalogue.register(_copy_of("climate_box", "climate_box", random_seed=99))
    assert catalogue.entry("climate_box") is PACKAGED.entry("climate_box")


@pytest.mark.parametrize("name", ["Drafted", "drafted-box", "drafted.box", "", "box/1"])
def test_a_scenario_is_named_as_a_manifest_is(name: str) -> None:
    with pytest.raises(ScenarioRefused, match="lowercase"):
        Catalogue().register(_copy_of("climate_box", name))


def test_one_simulators_scenarios_are_its_own() -> None:
    first, second = Catalogue(), Catalogue()
    first.register(_copy_of("climate_box", "drafted_box"))

    assert second.entry("drafted_box") is None
    assert second.ids() == manifest_ids()


def test_a_scenario_registered_at_once_by_many_is_registered_once() -> None:
    catalogue = Catalogue()

    with ThreadPoolExecutor(max_workers=REGISTERING) as pool:
        entries = list(
            pool.map(
                lambda _: catalogue.register(_copy_of("climate_box", "drafted_box")),
                range(REGISTERING),
            )
        )

    assert all(entry is entries[0] for entry in entries)
    assert catalogue.ids() == [*manifest_ids(), "drafted_box"]


def test_both_catalogues_answer_as_scenarios() -> None:
    catalogues: list[Scenarios] = [PACKAGED, Catalogue(), PackagedScenarios([])]

    assert [catalogue.entry("climate_box") is not None for catalogue in catalogues] == [
        True,
        True,
        False,
    ]
