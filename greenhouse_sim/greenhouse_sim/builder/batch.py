"""Edits of many parts of a draft at once (P12.0).

Each edit checks all it is asked to change before changing anything, and
returns a new draft, so that an editor keeps the one before for its undo.
"""

from collections.abc import Iterable

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.installation import Installation, RowCrop


def assign_crop_to_rows(
    draft: Installation, rows: Iterable[int], *, crop_model: CropModel, variety: str
) -> Installation:
    """A draft whose chosen rows grow one crop, every other row as before.
    Refused, changing nothing, if no row is chosen, if a row is not one of
    the layout's, or if the crop is not one a row can grow. Choosing a row
    twice, or giving rows the crop they grow, changes nothing more."""
    chosen = set(rows)
    total = 0 if draft.layout.crop_rows is None else draft.layout.crop_rows.rows
    if not chosen:
        raise ValueError("choose at least one row")
    if any(isinstance(row, bool) or not isinstance(row, int) for row in chosen):
        raise ValueError("rows are chosen by their numbers")
    if any(not 1 <= row <= total for row in chosen):
        raise ValueError(f"choose rows from 1 to {total}")
    crops = {crop.row: crop for crop in draft.row_crops}
    for row in chosen:
        crops[row] = RowCrop(row=row, crop_model=crop_model, variety=variety)
    return draft.model_copy(update={"row_crops": [crops[row] for row in sorted(crops)]})
