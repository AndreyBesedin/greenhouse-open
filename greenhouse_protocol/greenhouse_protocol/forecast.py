"""A forecast: what a named provider said, at an instant, a quantity would
be at a moment or over a period (decision 0061).

A forecast is a record of its own, not an observation: what it is for lies
after what was known when it was made. A policy is given forecasts only
from the providers its information budget names
(`greenhouse_protocol.budget`), and its port delivers each no earlier than
its issue (`greenhouse_protocol.contracts.policy`). A recorded dataset that
carries a forecast as a reading, such as the day's radiation sum a
climate computer was told, keeps it as an observation
(`FORECAST_RADIATION_SUM_TODAY_J_CM2`).
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.instant import Instant

type Name = Annotated[str, StringConstraints(min_length=1)]


class Forecast(BaseModel):
    """One forecast value: by whom, when it was issued, what it is for, and
    how sure its provider is. A moment's forecast is for the instant
    `valid_from`, which `valid_until` repeats; a period's is the quantity
    over it as its type has it, a level's mean or a sum's total."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    forecast_id: Identifier
    greenhouse_id: Name
    # The compartment it is for, when the greenhouse has compartments; None
    # for the greenhouse or its site as a whole.
    compartment_id: Name | None = None
    # The provider, as the budget names it, and its version.
    provider_id: Identifier
    provider_version: Name
    # When the provider made it: the port delivers it no earlier.
    issued_at: Instant
    valid_from: Instant
    valid_until: Instant
    quantity: ObservationType
    # In the quantity's unit, as its type names it.
    value: float
    # Its error's standard deviation, in the same unit, when its provider
    # states one.
    standard_deviation: Annotated[float, Field(ge=0.0)] | None = None

    @model_validator(mode="after")
    def _ends_no_earlier_than_it_starts(self) -> Self:
        if self.valid_until < self.valid_from:
            raise ValueError(
                f"forecast {self.forecast_id!r} is valid until "
                f"{self.valid_until.isoformat()}, before it is valid from "
                f"{self.valid_from.isoformat()}"
            )
        return self
