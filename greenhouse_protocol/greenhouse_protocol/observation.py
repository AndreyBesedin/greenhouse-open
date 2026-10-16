"""A reading of the greenhouse: what was measured, of what, when, and where it
came from.

A reading may say which instrument took it (`sensor_id`), when it reached
whoever records it, if later than it was taken (`delivered_at`), and what is
known of its quality (`quality`). Older records, and sources that know none
of this, leave them unset, and they are written as before. A gap in a
sensor's readings is an absent record, not a flagged one.
"""

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from greenhouse_protocol.enums import ObservationQuality, ObservationType
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.provenance import RecordSource


def _unset(value: object) -> bool:
    return value is None or value == frozenset()


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: str
    greenhouse_id: str
    # The compartment this reading describes, when the greenhouse has
    # compartments; None scopes it to the greenhouse as a whole.
    compartment_id: str | None = None
    plant_id: str | None
    timestamp: Instant
    observation_type: ObservationType
    value: float
    source: RecordSource
    # The instrument that took the reading, when it is known.
    sensor_id: str | None = Field(default=None, exclude_if=_unset)
    # When the reading was delivered, if after it was taken (`timestamp`).
    delivered_at: Instant | None = Field(default=None, exclude_if=_unset)
    # What is known of the reading's quality; none, for a plain reading.
    quality: frozenset[ObservationQuality] = Field(default=frozenset(), exclude_if=_unset)

    @field_serializer("quality", when_used="json")
    def _sorted(self, quality: frozenset[ObservationQuality]) -> list[str]:
        # A set's order follows its members' hashes, which a string's vary
        # from one process to the next: written in order, the same reading
        # is the same bytes.
        return sorted(quality)
