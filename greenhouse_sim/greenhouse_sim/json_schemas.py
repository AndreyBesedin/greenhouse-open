"""How the simulator publishes a JSON Schema (audit W13, `AUDIT.9`): in
the 2020-12 dialect, which Pydantic generates and each schema names as its
`$schema`, and written to its file one way. `tests/test_published_schemas.py` lists every
schema published, holds each committed file to its export, and writes them
all:

    python tests/test_published_schemas.py --update

This module imports nothing from the simulator, so any part may use it.
"""

import json
from collections.abc import Mapping
from typing import Final

JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"


def schema_text(schema: Mapping[str, object]) -> str:
    """A schema as its published file holds it: indented, its text as it
    is, and ending with a new line."""
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
