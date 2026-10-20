"""What tells one thing from another, shortened (audit W13, `AUDIT.9`): a
scenario's manifest, a run, a checkpoint and a replay's day are each named
by the leading hexadecimal digits of the SHA-256 of their text, each at a
length of its own. A digest of a whole file, or of a CFD case's files, is
kept whole where it is made.

This module imports nothing from the simulator, so any part may use it.
"""

import hashlib


def short_digest(text: str, length: int) -> str:
    """The first `length` hexadecimal digits of the SHA-256 of `text`, as
    UTF-8."""
    return hashlib.sha256(text.encode()).hexdigest()[:length]
