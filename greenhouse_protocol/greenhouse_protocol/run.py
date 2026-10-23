"""A run's epoch, named: what a run continues from, and what an action was
carried from (decision 0046). A run and its epochs are the consumer
interface's (decision 0040, `greenhouse_protocol.contracts.consumer`)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class RunEpoch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    run_id: Annotated[str, StringConstraints(min_length=1)]
    epoch: Annotated[int, Field(ge=0)]
