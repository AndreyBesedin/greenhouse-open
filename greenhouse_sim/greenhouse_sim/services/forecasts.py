"""The forecasts a policy's port can serve (P15.6, decision 0061): each
from a provider its information budget names (`greenhouse_protocol.budget`),
issued no earlier than what it is made from is known.

A `Forecaster` is the simulator's side of one provider: given the
observations a port has delivered, it issues the forecasts that fall due in
a stretch of the run's time. It reads those observations and nothing of the
simulated world, so that a policy given a forecaster of this kind has
nothing a baseline fed the same observations could not have.

The first provider is persistence (`PERSISTENCE`): at the start of each
day after the first, it forecasts each hour of the day ahead for the
outside air as the last day's mean for the same hour of it, from the
readings delivered by then. It states no uncertainty. It forecasts the
outside air's temperature and relative humidity, the outside quantities a
run's weather station reads; outside radiation is not one of them, so it
is not forecast.
"""

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final, Protocol

from greenhouse_protocol.budget import (
    ForecastProvider,
    ForecastUncertainty,
    InformationBasis,
    InformationBudget,
)
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.observation import Observation

from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.units import DAY_S, HOUR_S

PERSISTENCE_ID: Final = "persistence"
PERSISTENCE_VERSION: Final = "1"
# What persistence forecasts: the outside air a weather station reads.
PERSISTED: Final = frozenset(
    {ObservationType.OUTSIDE_AIR_TEMPERATURE_C, ObservationType.OUTSIDE_RELATIVE_HUMIDITY_PCT}
)
HOUR: Final = timedelta(seconds=HOUR_S)


class Forecaster(Protocol):
    """One provider's forecasts, issued from a port's observations."""

    @property
    def provider(self) -> ForecastProvider: ...

    def issue_due(
        self,
        observed: Sequence[Observation],
        *,
        start: datetime,
        greenhouse_id: str,
        after: datetime | None,
        until: datetime,
    ) -> list[Forecast]:
        """The forecasts issued after `after` (from the run's start, if
        none) and no later than `until`, in the order they were issued,
        from `observed`, which are the readings delivered by `until`."""
        ...


class Persistence:
    """Tomorrow's outside air as today's was: see the module."""

    provider = ForecastProvider(
        provider_id=PERSISTENCE_ID,
        version=PERSISTENCE_VERSION,
        basis=InformationBasis.OBSERVED,
        quantities=PERSISTED,
        issued_every_s=DAY_S,
        horizon_s=DAY_S,
        uncertainty=ForecastUncertainty.NONE,
    )

    def issue_due(
        self,
        observed: Sequence[Observation],
        *,
        start: datetime,
        greenhouse_id: str,
        after: datetime | None,
        until: datetime,
    ) -> list[Forecast]:
        every = timedelta(seconds=self.provider.issued_every_s)
        # The k-th issue is k days into the run: the first has a day of
        # readings to persist.
        first = 1 if after is None else max(1, (after - start) // every + 1)
        last = (until - start) // every
        forecasts: list[Forecast] = []
        for k in range(first, last + 1):
            forecasts += self._issued(observed, start, greenhouse_id, k, every)
        return forecasts

    def _issued(
        self,
        observed: Sequence[Observation],
        start: datetime,
        greenhouse_id: str,
        k: int,
        every: timedelta,
    ) -> list[Forecast]:
        issued_at = start + k * every
        since = issued_at - every
        by_hour: dict[tuple[ObservationType, int], list[float]] = defaultdict(list)
        for reading in observed:
            if (
                reading.observation_type in self.provider.quantities
                and since <= reading.timestamp < issued_at
                and (reading.delivered_at or reading.timestamp) <= issued_at
            ):
                by_hour[(reading.observation_type, (reading.timestamp - since) // HOUR)].append(
                    reading.value
                )
        return [
            Forecast(
                forecast_id=f"{PERSISTENCE_ID}-{quantity}-d{k}-h{hour}",
                greenhouse_id=greenhouse_id,
                provider_id=PERSISTENCE_ID,
                provider_version=PERSISTENCE_VERSION,
                issued_at=issued_at,
                valid_from=issued_at + hour * HOUR,
                valid_until=issued_at + (hour + 1) * HOUR,
                quantity=quantity,
                value=math.fsum(values) / len(values),
            )
            for (quantity, hour), values in sorted(by_hour.items())
        ]


PERSISTENCE: Final = Persistence()


def persistence_budget(observed: frozenset[ObservationType]) -> InformationBudget:
    """The budget of persistence, forecasting the outside quantities of
    `observed` that it does: refused where the run observes none."""
    quantities = PERSISTED & observed
    if not quantities:
        raise InvalidRequest(
            "persistence forecasts the outside air, and the run observes none of it"
        )
    return InformationBudget(
        budget_id=PERSISTENCE_ID,
        forecasts=(PERSISTENCE.provider.model_copy(update={"quantities": quantities}),),
    )
