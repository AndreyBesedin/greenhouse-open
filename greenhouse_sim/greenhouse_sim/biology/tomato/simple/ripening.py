from greenhouse_sim.biology.tomato.simple.parameters import (
    IMMATURE_GREEN_FROM_PROGRESS,
    MATURE_GREEN_FROM_PROGRESS,
    OVERRIPE_AFTER_DAYS,
    REFERENCE_TEMPERATURE_C,
    RIPENING_MIN_TIME_FACTOR,
    RIPENING_SPEEDUP_PER_DEGREE,
    TURNING_FROM_PROGRESS,
)
from greenhouse_sim.biology.tomato.simple.state import SimpleFruitState
from greenhouse_sim.world.state import Fruit, FruitStatus, GreenhouseEnvironment, RipenessStage


def effective_ripening_day(
    fruit_state: SimpleFruitState, environment: GreenhouseEnvironment
) -> float:
    """Warmer greenhouses ripen fruit faster."""
    temp_factor = 1.0 - RIPENING_SPEEDUP_PER_DEGREE * (
        environment.air_temperature_c - REFERENCE_TEMPERATURE_C
    )
    return fruit_state.ripening_day * max(RIPENING_MIN_TIME_FACTOR, temp_factor)


def ripeness_stage(
    fruit: Fruit, fruit_state: SimpleFruitState, environment: GreenhouseEnvironment
) -> RipenessStage:
    ripening_day = effective_ripening_day(fruit_state, environment)
    progress = fruit.age_days / ripening_day if ripening_day > 0 else 1.0

    if progress >= 1.0 + OVERRIPE_AFTER_DAYS / max(ripening_day, 1.0):
        return RipenessStage.OVERRIPE
    if progress >= 1.0:
        return RipenessStage.RIPE
    if progress >= TURNING_FROM_PROGRESS:
        return RipenessStage.TURNING
    if progress >= MATURE_GREEN_FROM_PROGRESS:
        return RipenessStage.MATURE_GREEN
    if progress >= IMMATURE_GREEN_FROM_PROGRESS:
        return RipenessStage.IMMATURE_GREEN
    return RipenessStage.FRUIT_SET


def advance_ripening(
    fruit: Fruit, fruit_state: SimpleFruitState, environment: GreenhouseEnvironment
) -> Fruit:
    stage = ripeness_stage(fruit, fruit_state, environment)
    status = fruit.status
    if fruit.status == FruitStatus.GROWING and stage in (
        RipenessStage.RIPE,
        RipenessStage.OVERRIPE,
    ):
        status = FruitStatus.RIPE
    return fruit.model_copy(update={"ripeness_stage": stage, "status": status})
