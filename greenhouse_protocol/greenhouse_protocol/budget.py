"""What a policy is given to decide with, beyond the observations and the
clock, which it always has: its information budget (decision 0061).

A budget names, for one episode:

- **forecasts,** each provider with its version, the quantities it
  forecasts, how often it issues, how far ahead, and how it states its
  uncertainty;
- **prediction models and calibrations,** each a versioned asset given
  explicitly, with its digest.

Each says what it is made from (`InformationBasis`). Policies are compared
only on budgets alike, so a budget that gives a policy anything of the
simulated world's truth (its future, its state, its parameters) says so:
it is an oracle, a privileged reference, never a matched comparator. The
label is checked, not inferred: a budget that gives the truth and is not
labelled is refused, and so is a label on one that does not.
"""

from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    StringConstraints,
    field_serializer,
    model_validator,
)
from pydantic.config import JsonDict

from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.enums import ObservationType

type Name = Annotated[str, StringConstraints(min_length=1)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

# A forecast provider or an asset made from the simulated world's truth, as
# the published schema matches it.
_PRIVILEGED: Final[JsonDict] = {
    "properties": {"basis": {"const": "privileged"}},
    "required": ["basis"],
}


class InformationBasis(StrEnum):
    """What a forecast or an asset is made from."""

    # The run's own observations, up to the moment it is made: nothing a
    # matched baseline could not have.
    OBSERVED = "observed"
    # Outside the run, as a greenhouse gets it: a weather service's
    # forecast, a published calibration.
    EXTERNAL = "external"
    # The simulated world's truth: its future, its state or its parameters.
    PRIVILEGED = "privileged"


class ForecastUncertainty(StrEnum):
    """How a provider's forecasts state their uncertainty."""

    NONE = "none"  # they state none
    STANDARD_DEVIATION = "standard_deviation"  # each gives its error's standard deviation


class ForecastProvider(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    provider_id: Identifier
    version: Name
    basis: InformationBasis
    quantities: Annotated[frozenset[ObservationType], Field(min_length=1)]
    # How often it issues a forecast, and how far ahead of its issue the
    # latest moment it forecasts lies, in seconds.
    issued_every_s: PositiveFloat
    horizon_s: PositiveFloat
    uncertainty: ForecastUncertainty

    @field_serializer("quantities", when_used="json")
    def _in_order(self, quantities: frozenset[ObservationType]) -> list[str]:
        # Written in order, the same budget is the same bytes.
        return sorted(quantities)


class AssetKind(StrEnum):
    PREDICTION_MODEL = "prediction_model"
    CALIBRATION = "calibration"


class PredictionAsset(BaseModel):
    """A prediction model or a calibration a policy is given: named,
    versioned, and pinned by its bytes' digest."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    asset_id: Identifier
    kind: AssetKind
    version: Name
    sha256: Sha256
    basis: InformationBasis


class InformationBudget(BaseModel):
    """An episode's budget: see the module."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        # Labelled exactly when it gives the truth, as the published schema
        # says it too.
        json_schema_extra={
            "if": {
                "anyOf": [
                    {"properties": {"full_state": {"const": True}}, "required": ["full_state"]},
                    {
                        "properties": {"forecasts": {"contains": _PRIVILEGED}},
                        "required": ["forecasts"],
                    },
                    {"properties": {"assets": {"contains": _PRIVILEGED}}, "required": ["assets"]},
                ]
            },
            "then": {"properties": {"oracle": {"const": True}}, "required": ["oracle"]},
            "else": {"properties": {"oracle": {"const": False}}},
        },
    )

    budget_id: Identifier
    forecasts: tuple[ForecastProvider, ...] = ()
    assets: tuple[PredictionAsset, ...] = ()
    # Whether the policy is given the simulated world's state, which only a
    # reference in the simulator's process reads, never through a port.
    full_state: bool = False
    # Labelled exactly when it gives the truth: the full state, or a
    # privileged forecast or asset.
    oracle: bool = False

    @model_validator(mode="after")
    def _named_once_and_labelled(self) -> Self:
        providers = [provider.provider_id for provider in self.forecasts]
        if len(set(providers)) != len(providers):
            raise ValueError("a forecast provider is named more than once")
        assets = [asset.asset_id for asset in self.assets]
        if len(set(assets)) != len(assets):
            raise ValueError("an asset is named more than once")
        if self.oracle != self.gives_the_truth():
            raise ValueError(
                "a budget is labelled an oracle exactly when it gives the truth: "
                "the full state, or a privileged forecast or asset"
            )
        return self

    def gives_the_truth(self) -> bool:
        """Whether anything it gives is the simulated world's truth."""
        return (
            self.full_state
            or any(p.basis == InformationBasis.PRIVILEGED for p in self.forecasts)
            or any(a.basis == InformationBasis.PRIVILEGED for a in self.assets)
        )

    def provider(self, provider_id: str) -> ForecastProvider | None:
        return next((p for p in self.forecasts if p.provider_id == provider_id), None)


# The budget of a policy given nothing beyond the observations and the
# clock.
OBSERVATIONS_ONLY: Final = InformationBudget(budget_id="observations_only")
