"""How far the simulator's readings sit from what was really the case.

The first consumer of `greenhouse_sim.ground_truth`, and the reason that
interface exists. A published observation is a noisy measurement of a
quantity the simulator knows exactly; comparing the two says how hard the
reconstruction problem a consumer faces actually is.

Nothing here informs a decision: it scores the sensing, so that work on
perception and state reconstruction has a baseline to beat rather than an
impression.
"""

from collections import defaultdict
from statistics import fmean

from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel

from greenhouse_sim.ground_truth import GroundTruth

# Which true quantity each reading is a measurement of.
_PLANT_QUANTITY: dict[ObservationType, str] = {
    ObservationType.SOIL_MOISTURE_PCT: "soil_moisture_pct",
    ObservationType.VISIBLE_FRUIT_COUNT: "visible_fruit_count",
    ObservationType.RIPE_FRUIT_COUNT: "ripe_fruit_count",
    ObservationType.ESTIMATED_RIPE_MASS_G: "ripe_mass_g",
    ObservationType.VISIBLE_HEIGHT_CM: "visible_height_cm",
}


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
    greenhouse_id: str
    readings: int
    by_type: list[AccuracyByType]

    def for_type(self, observation_type: ObservationType) -> AccuracyByType:
        for entry in self.by_type:
            if entry.observation_type == observation_type:
                return entry
        raise LookupError(f"no readings of {observation_type!r} were scored")


def observation_accuracy(
    observations: list[Observation], truth: list[GroundTruth]
) -> AccuracyReport:
    """Scores readings against the truth recorded at the same instant.

    A reading with no matching ground truth is skipped rather than counted
    as an error: it means the caller collected the two at different
    instants, which is a gap in the evaluation, not in the sensor.
    """
    by_instant = {(t.greenhouse_id, t.timestamp): t for t in truth}
    errors: dict[ObservationType, list[tuple[float, float]]] = defaultdict(list)

    for observation in observations:
        at = by_instant.get((observation.greenhouse_id, observation.timestamp))
        if at is None:
            continue
        true_value = _true_value(observation, at)
        if true_value is None:
            continue
        errors[observation.observation_type].append(
            (abs(observation.value - true_value), true_value)
        )

    greenhouse_id = truth[0].greenhouse_id if truth else ""
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
        greenhouse_id=greenhouse_id,
        readings=sum(entry.readings for entry in by_type),
        by_type=by_type,
    )


def _true_value(observation: Observation, truth: GroundTruth) -> float | None:
    if observation.plant_id is None:
        if observation.observation_type == ObservationType.AIR_TEMPERATURE_C:
            return truth.air_temperature_c
        return None
    quantity = _PLANT_QUANTITY.get(observation.observation_type)
    if quantity is None:
        return None
    try:
        plant = truth.plant(observation.plant_id)
    except LookupError:
        return None
    return float(getattr(plant, quantity))
