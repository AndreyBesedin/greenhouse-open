"""Import and export an installation without a database or a Git checkout.

Format 1 preserves the portable installation definition exactly. A referenced
biological implementation must still be available to a simulator; no Python
code or runnable model is imported from an untrusted document.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from greenhouse_sim.builder.installation import InstallationDraft

# Bound an untrusted document before parsing. The editor can surface this
# restriction in the file picker and need not unpack arbitrary archives.
MAX_IMPORT_BYTES = 8_000_000


class InstallationFile(BaseModel):
    """Versioned, standalone document, independent of the local draft store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: Literal["greenhouse-open.installation"] = "greenhouse-open.installation"
    format_version: Literal[1] = 1
    installation: InstallationDraft


def export_installation(draft: InstallationDraft) -> str:
    """The portable JSON file for an installation, including its row crops."""
    return InstallationFile(installation=draft).model_dump_json(indent=2) + "\n"


def import_installation(document: str) -> InstallationDraft:
    """Read the same format; reject unknown versions and malformed models.

    A document can be imported into a separate draft database, or used
    directly as an installation, without modifying published templates.
    """
    if len(document.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ValueError(f"an installation file must not exceed {MAX_IMPORT_BYTES} bytes")
    try:
        return InstallationFile.model_validate_json(document).installation
    except ValidationError as error:
        raise ValueError("not a supported greenhouse installation file") from error
