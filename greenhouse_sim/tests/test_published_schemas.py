"""Every JSON Schema the simulator publishes, from one list (audit W13,
`AUDIT.9`): each committed file is its export, written one way
(`greenhouse_sim.json_schemas.schema_text`), in the dialect it names.

After a model they describe changes, they are written again, from
`greenhouse_sim/`:

    python tests/test_published_schemas.py --update

The scene's schema is written with the example scenes too, by
`tests/test_scene_schema.py --update`.

Each service's answer the viewer reads is published from the type the
service returns (audit W12, `AUDIT.8`), for the viewer to generate its side
of it from (`web/scripts/generateContractSources.ts`).
"""

import json
import sys
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import Annotated, Final, Literal

import pytest
from pydantic import BaseModel, Field

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.builder.portable import INSTALLATION_SCHEMA_FILE, installation_json_schema
from greenhouse_sim.cfd.geometry import cfd_geometry_json_schema
from greenhouse_sim.climate.glazing import GlazingAt
from greenhouse_sim.climate.house import HouseTrace
from greenhouse_sim.climate.openings import OpeningsAt
from greenhouse_sim.climate.probes import ClimateProbes
from greenhouse_sim.fields.field import field_json_schema
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT, answer_json_schema, schema_text
from greenhouse_sim.scenarios.layout_files import LAYOUT_SCHEMA_FILE, layout_json_schema
from greenhouse_sim.scenarios.manifest_files import MANIFEST_SCHEMA_FILE, manifest_json_schema
from greenhouse_sim.scene.snapshot import snapshot_json_schema
from greenhouse_sim.services.checkpoints import CheckpointSummary
from greenhouse_sim.services.crop import CropPlant, PlantsLight
from greenhouse_sim.services.fields import EquipmentAt, FieldNames
from greenhouse_sim.services.live import LiveState
from greenhouse_sim.services.plants import LabChecks
from greenhouse_sim.services.playback import PlaybackState
from greenhouse_sim.services.run_state import RunState
from greenhouse_sim.services.scenarios import RunManifest, ScenarioSummary
from greenhouse_sim.services.sensors import SensorObservations, SensorTruths
from greenhouse_sim.services.system import Version
from greenhouse_sim.services.timeline import TimelineDocument
from greenhouse_sim.services.weather import WeatherAtAMoment, WeatherThroughADay

PACKAGE: Final = Path(__file__).resolve().parents[1] / "greenhouse_sim"
SNAPSHOT_SCHEMA_FILE: Final = PACKAGE / "scene" / "snapshot.schema.json"
SERVICES: Final = PACKAGE / "services"
CLIMATE: Final = PACKAGE / "climate"

# Each answer of a service the viewer reads: its schema's file, beside the
# module of the type the service returns, and that type. A list the viewer
# reads one by one (the scenarios, the checkpoints) is published as its item.
ANSWERS: Final[dict[Path, type[object]]] = {
    SERVICES / "version.schema.json": Version,
    SERVICES / "scenario_summary.schema.json": ScenarioSummary,
    SERVICES / "run_manifest.schema.json": RunManifest,
    SERVICES / "run_state.schema.json": RunState,
    SERVICES / "observations.schema.json": SensorObservations,
    SERVICES / "truth.schema.json": SensorTruths,
    SERVICES / "weather.schema.json": WeatherAtAMoment,
    SERVICES / "weather_day.schema.json": WeatherThroughADay,
    SERVICES / "equipment.schema.json": EquipmentAt,
    SERVICES / "field_names.schema.json": FieldNames,
    SERVICES / "timeline.schema.json": TimelineDocument,
    SERVICES / "checkpoint.schema.json": CheckpointSummary,
    SERVICES / "playback.schema.json": PlaybackState,
    SERVICES / "live.schema.json": LiveState,
    SERVICES / "plants_light.schema.json": PlantsLight,
    SERVICES / "crop_plant.schema.json": CropPlant,
    SERVICES / "lab_checks.schema.json": LabChecks,
    SERVICES / "lab_environments.schema.json": dict[str, LocalEnvironment],
    PACKAGE / "biology" / "tomato" / "organ" / "plant.schema.json": Plant,
    CLIMATE / "house.schema.json": HouseTrace,
    CLIMATE / "probes.schema.json": ClimateProbes,
    CLIMATE / "glazing.schema.json": GlazingAt,
    CLIMATE / "openings.schema.json": OpeningsAt,
}

# Each published schema's file, and the export it holds.
PUBLISHED: Final[dict[Path, Callable[[], Mapping[str, object]]]] = {
    SNAPSHOT_SCHEMA_FILE: snapshot_json_schema,
    PACKAGE / "fields" / "field.schema.json": field_json_schema,
    PACKAGE / "cfd" / "geometry.schema.json": cfd_geometry_json_schema,
    MANIFEST_SCHEMA_FILE: manifest_json_schema,
    LAYOUT_SCHEMA_FILE: layout_json_schema,
    INSTALLATION_SCHEMA_FILE: installation_json_schema,
    **{path: partial(answer_json_schema, answered) for path, answered in ANSWERS.items()},
}


@pytest.mark.parametrize("path", sorted(PUBLISHED), ids=lambda path: path.name)
def test_each_published_schema_is_its_export(path: Path) -> None:
    assert path.read_text() == schema_text(PUBLISHED[path]()), (
        f"{path.name} drifted: python tests/test_published_schemas.py --update"
    )


@pytest.mark.parametrize("path", sorted(PUBLISHED), ids=lambda path: path.name)
def test_each_published_schema_names_its_dialect(path: Path) -> None:
    assert json.loads(path.read_text())["$schema"] == JSON_SCHEMA_DIALECT


class _Box(BaseModel):
    kind: Literal["box"] = "box"
    size_m: float


class _Ball(BaseModel):
    kind: Literal["ball"] = "ball"
    radius_m: float


class _Answer(BaseModel):
    count: int
    note: str = ""
    seen_by: str | None = Field(default=None, exclude_if=lambda seen_by: seen_by is None)
    shape: Annotated[_Box | _Ball, Field(discriminator="kind")]


def test_an_answer_requires_what_it_always_sends() -> None:
    schema = answer_json_schema(_Answer)

    assert schema["required"] == ["count", "note", "shape"]
    definitions = schema["$defs"]
    assert isinstance(definitions, dict)
    assert definitions["_Box"] == {
        "properties": {
            "kind": {"const": "box", "default": "box", "title": "Kind", "type": "string"},
            "size_m": {"title": "Size M", "type": "number"},
        },
        "required": ["kind", "size_m"],
        "title": "_Box",
        "type": "object",
    }


def test_an_answer_leaves_out_what_is_not_json_schema() -> None:
    schema = answer_json_schema(list[_Answer])

    assert "discriminator" not in json.dumps(schema)
    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["items"] == {"$ref": "#/$defs/_Answer"}


def write_schemas() -> list[Path]:
    """Writes every published schema from its export, and says which."""
    for path, export in PUBLISHED.items():
        path.write_text(schema_text(export()))
    return list(PUBLISHED)


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_published_schemas.py --update")
    for written in write_schemas():
        print(f"wrote {written}")
