"""What a greenhouse's items are named by: the identifiers of its equipment,
its sensors and its doors and vents (#254).

The API's parameters write these identifiers between marks, `:` and `,`
(`set=heater:1`, `schedule=600:heater:1`, `openings=roof_vent:0.5`), and
after `~` in a layout's moves (`layout=default~heater:1:0`), and its routes
decode a query before they read it, so escaping a mark would not help. An
identifier holds only what none of them mark: letters, digits, `_`, `.` and
`-`. A scenario or layout that names an item otherwise is refused as it is
read, rather than holding an item no request could name.
"""

from typing import Annotated, Final

from pydantic import Field

ITEM_ID_PATTERN: Final = r"^[A-Za-z0-9_.-]+$"

ItemId = Annotated[
    str,
    Field(
        pattern=ITEM_ID_PATTERN,
        description=(
            "Letters, digits, '_', '.' and '-' only: the API's parameters write it "
            "between ':' and ','."
        ),
    ),
]
