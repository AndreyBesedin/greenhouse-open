"""Scenarios as manifests (P09.1): every scenario is read from its file, in
a format whose version it states, and a manifest the simulator cannot read
exactly is refused with the reason.

`greenhouse_sim/scenarios/scenario.schema.json` is the schema the manifests
name, generated here, from `greenhouse_sim/`:

    python tests/test_scenario_manifests.py --update
"""

import json
import sys
from datetime import date
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
    manifest_digest,
    manifest_ids,
    manifest_json_schema,
    scenario_from_manifest,
)
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.scenarios import RunManifest, run_manifest


def _manifest(scenario_id: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())
    return document


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


@pytest.mark.parametrize("scenario_id", manifest_ids())
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


def test_a_run_says_what_it_is_made_from() -> None:
    assert run_manifest("reference_greenhouse") == RunManifest(
        scenario_id="reference_greenhouse",
        schema_version=SCHEMA_VERSION,
        version=manifest_digest("reference_greenhouse"),
        random_seed=42,
        start_date=date(2026, 3, 1),
        duration_days=120,
        opening_day=80,
        crop_model="organ",
        variety="cherry_tomato",
        airflow="uniform",
        weather="default",
        weather_kind="synthetic",
        cloud_cover_pct=None,
        wind_from_deg=None,
    )


def test_a_run_under_another_weather_names_it_and_its_overrides() -> None:
    manifest = run_manifest("climate_box", "cold_spring_day@80~90")

    assert (manifest.weather, manifest.weather_kind) == ("cold_spring_day", "synthetic")
    assert (manifest.cloud_cover_pct, manifest.wind_from_deg) == (80.0, 90.0)
    # Its own, constant weather, its own seed and crop model.
    own = run_manifest("climate_box")
    assert (own.weather, own.weather_kind, own.random_seed) == ("default", "constant", 1201)
    assert (own.crop_model, own.opening_day) == ("simple", None)
    assert run_manifest("tomato_compartment").airflow == "buoyancy"


def test_a_run_manifest_is_refused_as_its_run_is() -> None:
    with pytest.raises(NotFound, match="no scenario"):
        run_manifest("nowhere")
    with pytest.raises(NotFound, match="no weather"):
        run_manifest("climate_box", "monsoon")
    with pytest.raises(InvalidRequest, match="cloud cover"):
        run_manifest("climate_box", "default@120")


def _update() -> None:
    schema = json.dumps(manifest_json_schema(), indent=2, ensure_ascii=False)
    MANIFEST_SCHEMA_FILE.write_text(schema + "\n")


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_scenario_manifests.py --update")
    _update()
    print(f"wrote {MANIFEST_SCHEMA_FILE}")
