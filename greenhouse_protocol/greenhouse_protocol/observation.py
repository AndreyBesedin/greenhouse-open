from datetime import datetime

from pydantic import BaseModel, ConfigDict

from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.provenance import RecordSource


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: str
    greenhouse_id: str
    # The compartment this reading describes, when the greenhouse has
    # compartments; None scopes it to the greenhouse as a whole.
    compartment_id: str | None = None
    plant_id: str | None
    timestamp: datetime
    observation_type: ObservationType
    value: float
    source: RecordSource
