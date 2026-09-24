"""Snapshot profiles: deterministic subsets of a source dataset sized for
different machines. A profile decides which artifact kinds may be fetched
and caps the download so `tiny` and `dev` can never silently become a
30 GB image pull."""

from dataclasses import dataclass
from enum import StrEnum

from greenhouse_adapters.manifests import ArtifactKind


class Profile(StrEnum):
    TINY = "tiny"
    DEV = "dev"
    FULL = "full"


@dataclass(frozen=True)
class ProfileRules:
    profile: Profile
    artifact_kinds: frozenset[ArtifactKind]
    max_download_bytes: int | None


_TABULAR = frozenset({ArtifactKind.METADATA, ArtifactKind.TIMESERIES})

PROFILES: dict[Profile, ProfileRules] = {
    # metadata + time series only; well under 1 GB by construction
    Profile.TINY: ProfileRules(Profile.TINY, _TABULAR, max_download_bytes=256 * 1024 * 1024),
    Profile.DEV: ProfileRules(Profile.DEV, _TABULAR, max_download_bytes=1024 * 1024 * 1024),
    # everything, including the image archives - opt in explicitly
    Profile.FULL: ProfileRules(Profile.FULL, frozenset(ArtifactKind), max_download_bytes=None),
}
