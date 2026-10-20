"""Every JSON Schema the simulator publishes, from one list (audit W13,
`AUDIT.9`): each committed file is its export, written one way
(`greenhouse_sim.json_schemas.schema_text`), in the dialect it names.

After a model they describe changes, they are written again, from
`greenhouse_sim/`:

    python tests/test_published_schemas.py --update

The scene's schema is written with the example scenes too, by
`tests/test_scene_schema.py --update`.
"""

import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.cfd.geometry import cfd_geometry_json_schema
from greenhouse_sim.fields.field import field_json_schema
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT, schema_text
from greenhouse_sim.scenarios.layout_files import LAYOUT_SCHEMA_FILE, layout_json_schema
from greenhouse_sim.scenarios.manifest_files import MANIFEST_SCHEMA_FILE, manifest_json_schema
from greenhouse_sim.scene.snapshot import snapshot_json_schema

PACKAGE: Final = Path(__file__).resolve().parents[1] / "greenhouse_sim"
SNAPSHOT_SCHEMA_FILE: Final = PACKAGE / "scene" / "snapshot.schema.json"

# Each published schema's file, and the export it holds.
PUBLISHED: Final[dict[Path, Callable[[], Mapping[str, object]]]] = {
    SNAPSHOT_SCHEMA_FILE: snapshot_json_schema,
    PACKAGE / "fields" / "field.schema.json": field_json_schema,
    PACKAGE / "cfd" / "geometry.schema.json": cfd_geometry_json_schema,
    MANIFEST_SCHEMA_FILE: manifest_json_schema,
    LAYOUT_SCHEMA_FILE: layout_json_schema,
}


@pytest.mark.parametrize("path", sorted(PUBLISHED), ids=lambda path: path.name)
def test_each_published_schema_is_its_export(path: Path) -> None:
    assert path.read_text() == schema_text(PUBLISHED[path]()), (
        f"{path.name} drifted: python tests/test_published_schemas.py --update"
    )


@pytest.mark.parametrize("path", sorted(PUBLISHED), ids=lambda path: path.name)
def test_each_published_schema_names_its_dialect(path: Path) -> None:
    assert json.loads(path.read_text())["$schema"] == JSON_SCHEMA_DIALECT


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
