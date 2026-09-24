"""Reading cells from the WUR workbooks."""

import math


def number_cell(row: tuple[object, ...], index: int) -> float | None:
    """A numeric cell, or None for an empty or NaN one. Any other text is
    refused: it would mean the column is not what the caller assumes."""
    if index >= len(row):
        return None
    cell = row[index]
    if cell is None or isinstance(cell, bool):
        return None
    if isinstance(cell, int | float):
        return None if math.isnan(cell) else float(cell)
    text = str(cell).strip()
    if text == "" or text.lower() == "nan":
        return None
    value = float(text)
    return None if math.isnan(value) else value
