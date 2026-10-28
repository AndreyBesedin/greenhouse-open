"""How far a run's readings sit from what was really the case.

The first consumer of `greenhouse_sim.ground_truth`, and the reason that
interface exists. A published observation is a noisy measurement of a
quantity the run knows exactly; comparing the two says how hard the
reconstruction problem a consumer faces actually is.

Nothing here informs a decision: it scores the sensing, so that work on
perception and state reconstruction has a baseline to beat rather than an
impression.
"""

from collections import defaultdict
from statistics import fmean
from typing import Final

from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel

from greenhouse_sim.ground_truth import GroundTruth, reading
from greenhouse_sim.units import FULL_TURN_DEG

# What is read round the compass: a reading's error is the shorter way round.
GOING_ROUND: Final = frozenset({ObservationType.OUTSIDE_WIND_DIRECTION_DEG})


class AccuracyByType(BaseModel):
    observation_type: ObservationType
    readings: int
    mean_absolute_error: float
    max_absolute_error: float
    mean_true_value: float

    @property
    def mean_relative_error(self) -> float:
        """Absolute error as a fraction of the average true value.

        Undefined when the quantity averages zero - early in a run there is
        no ripe fruit to weigh - and reported as zero rather than raising,
        because a run that never grows a fruit is a legitimate input.
        """
        if self.mean_true_value == 0:
            return 0.0
        return self.mean_absolute_error / abs(self.mean_true_value)


class AccuracyReport(BaseModel):
    run_id: str
    readings: int
    by_type: list[AccuracyByType]

    def for_type(self, observation_type: ObservationType) -> AccuracyByType:
        for entry in self.by_type:
            if entry.observation_type == observation_type:
                return entry
        raise LookupError(f"no readings of {observation_type!r} were scored")


def observation_accuracy(observations: list[Observation], truth: GroundTruth) -> AccuracyReport:
    """Scores a run's readings against what each truly measured.

    A reading with no true reading is skipped rather than counted as an
    error: one of another run, one taken after the truth's moment, or a
    modelled record, such as the heat given, which measures nothing. That is
    a gap in the evaluation, not in the sensor.
    """
    true = {each.reading(): each.value for each in truth.readings}
    errors: dict[ObservationType, list[tuple[float, float]]] = defaultdict(list)
    for observation in observations:
        if observation.source.source_id != truth.run_id:
            continue
        true_value = true.get(reading(observation))
        if true_value is None:
            continue
        errors[observation.observation_type].append(
            (_error(observation.observation_type, observation.value, true_value), true_value)
        )

    by_type = [
        AccuracyByType(
            observation_type=observation_type,
            readings=len(pairs),
            mean_absolute_error=fmean(error for error, _ in pairs),
            max_absolute_error=max(error for error, _ in pairs),
            mean_true_value=fmean(value for _, value in pairs),
        )
        for observation_type, pairs in sorted(errors.items(), key=lambda item: item[0].value)
    ]
    return AccuracyReport(
        run_id=truth.run_id,
        readings=sum(entry.readings for entry in by_type),
        by_type=by_type,
    )


def _error(observation_type: ObservationType, value: float, true_value: float) -> float:
    """How far a reading is from the truth: the shorter way round the
    compass, for a direction."""
    error = abs(value - true_value)
    if observation_type in GOING_ROUND:
        error %= FULL_TURN_DEG
        return min(error, FULL_TURN_DEG - error)
    return error
