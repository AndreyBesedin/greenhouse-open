from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from greenhouse_protocol.enums import EventSource, EventType


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    greenhouse_id: str
    # The compartment the event happened in, when the greenhouse has
    # compartments; None scopes it to the greenhouse as a whole.
    compartment_id: str | None = None
    plant_id: str | None
    timestamp: datetime
    event_type: EventType
    source: EventSource
    confidence: float = 1.0
    parameters: dict[str, Any] = Field(default_factory=dict)
