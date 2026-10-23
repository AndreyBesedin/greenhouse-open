"""Drafts of installations and their revisions, kept locally (P12.1,
decision 0051).

A draft is an installation being authored, kept at any step, runnable or
not, by its installation's identifier. Each save is a revision of it,
numbered from 1 and kept with the moment it was saved. An earlier revision
is reopened as it was, or made the latest again by reverting to it, which
saves it anew: nothing saved is lost but by deleting the draft.

A revision is kept as its installation's file (`builder.portable`), so that
one saved in an older format is read as the file would be, and a store
needs no migration of its own when the format changes.

The drafts are kept in one SQLite file, written a transaction at a time:
a save is kept whole or not at all. A save, revert or delete names the
revision it was made on, and is refused if another was saved since, as by
another window of the editor, rather than lose it (`StaleDraft`).
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from greenhouse_sim.builder.portable import export_installation, import_installation
from greenhouse_sim.scenarios.installation import Installation

# The version of the store's own tables, kept in the file's `user_version`.
STORE_FORMAT: Final = 1
# How long a save waits for another to finish writing, in seconds.
BUSY_TIMEOUT_S: Final = 5.0

_TABLES: Final = """
CREATE TABLE revisions (
    draft_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    saved_at TEXT NOT NULL,
    name TEXT NOT NULL,
    document TEXT NOT NULL,
    PRIMARY KEY (draft_id, revision)
) STRICT
"""


class DraftNotFound(LookupError):
    """A draft, or a revision of one, the store does not keep."""


class StaleDraft(ValueError):
    """A change made on a revision that is no longer the draft's latest, or
    a new draft under an identifier already kept."""


class DraftStoreError(ValueError):
    """A file that is not a store of drafts this simulator reads."""


@dataclass(frozen=True)
class Revision:
    """A draft as it was saved: its revision's number, when, and the
    installation."""

    draft_id: str
    revision: int
    saved_at: datetime
    installation: Installation


@dataclass(frozen=True)
class RevisionSummary:
    """A revision as a list of them shows it: its number, when it was
    saved, and its installation's name then."""

    revision: int
    saved_at: datetime
    name: str


@dataclass(frozen=True)
class DraftSummary:
    """A draft as a list of them shows it: its latest revision."""

    draft_id: str
    name: str
    revision: int
    saved_at: datetime


class DraftStore:
    """The drafts kept in one SQLite file, made, with its folder, if it is
    missing. Refused if the file is not a store of drafts in the format
    this simulator reads."""

    def __init__(self, path: Path, now: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self._path = path
        self._now = now
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._writing() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                empty = connection.execute("SELECT 1 FROM sqlite_master").fetchone() is None
                if version == 0 and empty:
                    connection.execute(_TABLES)
                    connection.execute(f"PRAGMA user_version = {STORE_FORMAT}")
                    version = STORE_FORMAT
        except sqlite3.DatabaseError as error:
            raise DraftStoreError(f"{path}: not a store of drafts: {error}") from None
        if version != STORE_FORMAT:
            raise DraftStoreError(
                f"{path}: a store of drafts in format {version}; this simulator reads "
                f"format {STORE_FORMAT}"
            )

    def save(self, installation: Installation, *, on: int | None) -> Revision:
        """Save `installation` as the next revision of its draft, made on
        revision `on`, or as a new draft if None. Refused, saving nothing, if
        `on` is not the draft's latest revision, or a new draft's identifier
        is kept already."""
        document = export_installation(installation)
        with self._writing() as connection:
            latest = _latest(connection, installation.installation_id)
            if latest != on:
                raise StaleDraft(_stale(installation.installation_id, latest, on))
            return self._insert(connection, installation, (latest or 0) + 1, document)

    def revert(self, draft_id: str, revision: int, *, on: int) -> Revision:
        """Save revision `revision` of a draft again, as its latest, made on
        revision `on`. Refused as `save` is, or if there is no such
        revision."""
        with self._writing() as connection:
            latest = _latest(connection, draft_id)
            if latest is None:
                raise DraftNotFound(f"no draft {draft_id!r}")
            if latest != on:
                raise StaleDraft(_stale(draft_id, latest, on))
            installation = _read(connection, draft_id, revision).installation
            return self._insert(
                connection, installation, latest + 1, export_installation(installation)
            )

    def delete(self, draft_id: str, *, on: int) -> None:
        """Forget a draft and every revision of it, made on revision `on`.
        Refused as `save` is."""
        with self._writing() as connection:
            latest = _latest(connection, draft_id)
            if latest is None:
                raise DraftNotFound(f"no draft {draft_id!r}")
            if latest != on:
                raise StaleDraft(_stale(draft_id, latest, on))
            connection.execute("DELETE FROM revisions WHERE draft_id = ?", (draft_id,))

    def open(self, draft_id: str, revision: int | None = None) -> Revision:
        """A draft at a revision, by default its latest."""
        with closing(self._connect()) as connection:
            if revision is None:
                latest = _latest(connection, draft_id)
                if latest is None:
                    raise DraftNotFound(f"no draft {draft_id!r}")
                revision = latest
            return _read(connection, draft_id, revision)

    def revisions(self, draft_id: str) -> list[RevisionSummary]:
        """Every revision of a draft, the first first."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT revision, saved_at, name FROM revisions WHERE draft_id = ? "
                "ORDER BY revision",
                (draft_id,),
            ).fetchall()
        if not rows:
            raise DraftNotFound(f"no draft {draft_id!r}")
        return [
            RevisionSummary(revision=revision, saved_at=datetime.fromisoformat(at), name=name)
            for revision, at, name in rows
        ]

    def drafts(self) -> list[DraftSummary]:
        """Every draft kept, by its identifier, as its latest revision is."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT draft_id, name, revision, saved_at FROM revisions AS kept "
                "WHERE revision = (SELECT MAX(revision) FROM revisions "
                "WHERE draft_id = kept.draft_id) ORDER BY draft_id"
            ).fetchall()
        return [
            DraftSummary(
                draft_id=draft_id, name=name, revision=revision, saved_at=datetime.fromisoformat(at)
            )
            for draft_id, name, revision, at in rows
        ]

    def _insert(
        self,
        connection: sqlite3.Connection,
        installation: Installation,
        revision: int,
        document: str,
    ) -> Revision:
        saved_at = self._now()
        connection.execute(
            "INSERT INTO revisions (draft_id, revision, saved_at, name, document) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                installation.installation_id,
                revision,
                saved_at.isoformat(),
                installation.name,
                document,
            ),
        )
        return Revision(
            draft_id=installation.installation_id,
            revision=revision,
            saved_at=saved_at,
            installation=installation,
        )

    def _connect(self) -> sqlite3.Connection:
        # A connection of its own for each call: the API answers requests
        # on threads of their own, and a connection stays on its thread.
        return sqlite3.connect(self._path, timeout=BUSY_TIMEOUT_S, isolation_level=None)

    @contextmanager
    def _writing(self) -> Iterator[sqlite3.Connection]:
        """A transaction that holds the file's write lock from its start, so
        that what it reads is still so when it writes: committed whole, or
        rolled back."""
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")


def _latest(connection: sqlite3.Connection, draft_id: str) -> int | None:
    found: int | None = connection.execute(
        "SELECT MAX(revision) FROM revisions WHERE draft_id = ?", (draft_id,)
    ).fetchone()[0]
    return found


def _read(connection: sqlite3.Connection, draft_id: str, revision: int) -> Revision:
    row = connection.execute(
        "SELECT saved_at, document FROM revisions WHERE draft_id = ? AND revision = ?",
        (draft_id, revision),
    ).fetchone()
    if row is None:
        raise DraftNotFound(f"no revision {revision} of draft {draft_id!r}")
    saved_at, document = row
    return Revision(
        draft_id=draft_id,
        revision=revision,
        saved_at=datetime.fromisoformat(saved_at),
        installation=import_installation(document),
    )


def _stale(draft_id: str, latest: int | None, on: int | None) -> str:
    if on is None:
        return f"a draft {draft_id!r} is kept already, at revision {latest}"
    if latest is None:
        return f"no draft {draft_id!r} to save revision {on} on"
    return f"draft {draft_id!r} is at revision {latest}, not {on}: another was saved since"
