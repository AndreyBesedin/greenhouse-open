from greenhouse_sim.world import Fruit, FruitStatus, GreenhouseEnvironment, RipenessStage

_OVERRIPE_BUFFER_DAYS = 8


def effective_ripening_day(fruit: Fruit, environment: GreenhouseEnvironment) -> float:
    """Warmer greenhouses ripen fruit faster."""
    temp_factor = 1.0 - 0.01 * (environment.air_temperature_c - 24.0)
    return fruit.ripening_day * max(0.6, temp_factor)


def ripeness_stage(fruit: Fruit, environment: GreenhouseEnvironment) -> RipenessStage:
    ripening_day = effective_ripening_day(fruit, environment)
    progress = fruit.age_days / ripening_day if ripening_day > 0 else 1.0

    if progress >= 1.0 + _OVERRIPE_BUFFER_DAYS / max(ripening_day, 1.0):
        return RipenessStage.OVERRIPE
    if progress >= 1.0:
        return RipenessStage.RIPE
    if progress >= 0.85:
        return RipenessStage.TURNING
    if progress >= 0.4:
        return RipenessStage.MATURE_GREEN
    if progress >= 0.1:
        return RipenessStage.IMMATURE_GREEN
    return RipenessStage.FRUIT_SET


def advance_ripening(fruit: Fruit, environment: GreenhouseEnvironment) -> Fruit:
    stage = ripeness_stage(fruit, environment)
    status = fruit.status
    if fruit.status == FruitStatus.GROWING and stage in (
        RipenessStage.RIPE,
        RipenessStage.OVERRIPE,
    ):
        status = FruitStatus.RIPE
    return fruit.model_copy(update={"ripeness_stage": stage, "status": status})
