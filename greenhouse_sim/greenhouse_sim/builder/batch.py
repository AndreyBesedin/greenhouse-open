"""Atomic authoring operations shared by the UI and imported workflows.

Each operation returns a new validated draft. The editor can place the
previous value on its undo stack and preview changes before committing.
"""

from collections.abc import Iterable

from greenhouse_sim.builder.installation import InstallationDraft, RowCrop


def assign_crop_to_rows(
    draft: InstallationDraft,
    selected_rows: Iterable[int],
    *,
    model_id: str,
    variety: str,
    model_revision: str | None = None,
) -> InstallationDraft:
    """Assign one crop to all selected rows without changing the other rows.

    Selection is validated in full before any replacement is returned.
    Re-applying the same assignment is idempotent.
    """
    selected = set(selected_rows)
    total = 0 if draft.layout.crop_rows is None else draft.layout.crop_rows.rows
    if not selected:
        raise ValueError("select at least one row")
    if any(
        isinstance(row, bool) or not isinstance(row, int) or not 1 <= row <= total
        for row in selected
    ):
        raise ValueError(f"select row numbers between 1 and {total}")

    # Validate the crop reference, variety and revision once even if all
    # selected rows were already assigned an identical crop.
    new = RowCrop(row=1, model_id=model_id, model_revision=model_revision, variety=variety)
    by_row = {row.row: row for row in draft.row_crops}
    for row in selected:
        by_row[row] = new.model_copy(update={"row": row})
    return InstallationDraft.model_validate(
        draft.model_dump()
        | {"row_crops": [by_row[row].model_dump() for row in sorted(by_row)]}
    )
