"""Scenarios as manifests (P09.1): every scenario is read from its file, in
a format whose version it states, and a manifest the simulator cannot read
exactly is refused with the reason.

`fixtures/scenarios_as_code.json` holds every scenario's configuration as
its Python module built it, before the scenarios became files: whatever
reads them now must build the same.

`greenhouse_sim/scenarios/scenario.schema.json` is the schema the manifests
name, generated here, from `greenhouse_sim/`:

    python tests/test_scenario_manifests.py --update
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.scenarios.manifest_files import (
    FIRST_SCENARIO,
    MANIFEST_SCHEMA_FILE,
    MANIFESTS_DIR,
    SCHEMA_FROM_A_MANIFEST_FILE,
    SCHEMA_VERSION,
    InvalidManifest,
    manifest_ids,
    manifest_json_schema,
    scenario_from_manifest,
)

AS_CODE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "scenarios_as_code.json").read_text()
)


def _manifest(scenario_id: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())
    return document


def test_the_same_scenarios_are_registered() -> None:
    assert set(SCENARIO_REGISTRY) == set(AS_CODE)


@pytest.mark.parametrize("scenario_id", sorted(AS_CODE))
def test_every_scenario_is_configured_as_its_code_was(scenario_id: str) -> None:
    assert SCENARIO_REGISTRY[scenario_id].model_dump(mode="json") == AS_CODE[scenario_id]


def test_the_published_manifest_schema_matches_the_configuration() -> None:
    assert json.loads(MANIFEST_SCHEMA_FILE.read_text()) == manifest_json_schema()


def test_the_schema_names_the_layout_and_refuses_what_it_does_not_have() -> None:
    schema: Any = manifest_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["properties"]["layout"]["type"] == "string"
    assert schema["properties"]["schema_version"] == {"const": SCHEMA_VERSION}
    assert "schema_version" in schema["required"]
    assert "Layout" not in schema["$defs"]


def test_every_scenario_has_a_manifest_and_the_first_is_listed_first() -> None:
    assert list(SCENARIO_REGISTRY) == manifest_ids()
    assert manifest_ids()[0] == FIRST_SCENARIO
    assert manifest_ids()[1:] == sorted(manifest_ids()[1:])


@pytest.mark.parametrize("scenario_id", sorted(AS_CODE))
def test_every_manifest_names_its_schema_its_format_and_its_layout(scenario_id: str) -> None:
    document = _manifest(scenario_id)

    assert document["$schema"] == SCHEMA_FROM_A_MANIFEST_FILE
    assert document["schema_version"] == SCHEMA_VERSION
    assert SCENARIO_REGISTRY[scenario_id].layout == load_layout(scenario_id, document["layout"])


def test_a_manifest_in_a_format_it_does_not_read_is_refused() -> None:
    for version in (SCHEMA_VERSION + 1, None, "1"):
        document = _manifest("climate_box") | {"schema_version": version}
        with pytest.raises(InvalidManifest, match="this simulator reads format 1"):
            scenario_from_manifest("climate_box", document)


def test_a_manifest_of_another_scenario_is_refused() -> None:
    with pytest.raises(InvalidManifest, match="describes 'climate_box'"):
        scenario_from_manifest("solar_lab", _manifest("climate_box"))


@pytest.mark.parametrize(
    ("change", "unknown"),
    [
        (lambda d: d | {"random_sed": 3}, "random_sed"),
        (lambda d: d | {"envelope": d["envelope"] | {"lenght": 12.0}}, "envelope.lenght"),
        (
            lambda d: (
                d
                | {
                    "envelope": d["envelope"]
                    | {
                        "openings": [
                            d["envelope"]["openings"][0] | {"centre": {"x": 0, "y": 1, "z": 2}}
                        ]
                    }
                }
            ),
            r"envelope.openings\[0\].centre.z",
        ),
    ],
)
def test_a_field_the_configuration_does_not_have_is_refused(change: Any, unknown: str) -> None:
    """At any depth, including where the models themselves would ignore it."""
    with pytest.raises(InvalidManifest, match=f"fields it does not have: {unknown}"):
        scenario_from_manifest("climate_box", change(_manifest("climate_box")))


def test_a_field_a_model_forbids_is_refused_by_the_model() -> None:
    document = _manifest("climate_box")

    with pytest.raises(ValidationError, match="wind_from"):
        scenario_from_manifest(
            "climate_box", document | {"weather": document["weather"] | {"wind_from": 90.0}}
        )


def test_notes_are_only_on_what_the_scenario_has() -> None:
    document = _manifest("climate_box")

    notes = document["notes"] | {"heaters": "two"}
    with pytest.raises(InvalidManifest, match="notes on what it does not have"):
        scenario_from_manifest("climate_box", document | {"notes": notes})
    with pytest.raises(InvalidManifest, match="notes are written by what each is about"):
        scenario_from_manifest("climate_box", document | {"notes": ["a note"]})


def test_a_manifest_names_a_layout_of_its_own_scenario() -> None:
    document = _manifest("tomato_compartment")

    assert scenario_from_manifest("tomato_compartment", document | {"layout": "propagation"})
    with pytest.raises(InvalidManifest, match="a layout is named"):
        scenario_from_manifest("tomato_compartment", document | {"layout": "../climate_box"})
    with pytest.raises(KeyError, match="no layout"):
        scenario_from_manifest("tomato_compartment", document | {"layout": "hydroponic"})


def _update() -> None:
    schema = json.dumps(manifest_json_schema(), indent=2, ensure_ascii=False)
    MANIFEST_SCHEMA_FILE.write_text(schema + "\n")


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_scenario_manifests.py --update")
    _update()
    print(f"wrote {MANIFEST_SCHEMA_FILE}")
