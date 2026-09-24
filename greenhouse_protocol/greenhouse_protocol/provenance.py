from pydantic import BaseModel, ConfigDict

from greenhouse_protocol.enums import SourceType


class RecordSource(BaseModel):
    """Where a piece of domain data came from - the system/run that
    produced it (SIMULATION, REAL_SENSORS, ...) plus, where meaningful, the
    id of that specific run/sensor/import (source_id) so the record stays
    traceable without requiring the record itself to carry a simulation-
    specific identity."""

    model_config = ConfigDict(frozen=True)

    type: SourceType
    source_id: str | None = None
