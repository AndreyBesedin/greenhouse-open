"""The simple tomato model's fixed parameters.

Hand-picked rather than calibrated, like the model itself. They are constants
of the model, not of a scenario: what a scenario may tune lives in
`ScenarioConfig`. Rates are per day and temperatures in degrees Celsius.
"""

from typing import Final

# The temperature at which growth, ripening and water use run at their
# reference rate. Each process speeds up or slows down away from it.
REFERENCE_TEMPERATURE_C: Final = 24.0

# Random draws made once, when a plant or a fruit is created: a plant's
# vigour scales its stem growth, a fruit's growth rate scales its age on the
# diameter curve. Both are drawn uniformly from (low, high).
PLANT_VIGOUR_RANGE: Final = (0.85, 1.15)
FRUIT_GROWTH_RATE_RANGE: Final = (0.85, 1.15)

# Stem growth. Full water stress removes this share of the day's growth.
STEM_GROWTH_LOSS_AT_FULL_WATER_STRESS: Final = 0.6
# Share of the day's growth lost per degree away from the reference
# temperature, and the smallest share that remains however far it is.
STEM_GROWTH_LOSS_PER_DEGREE: Final = 0.02
STEM_GROWTH_MIN_TEMPERATURE_FACTOR: Final = 0.5

# Ripening. Each degree above the reference temperature shortens the time to
# ripeness by this share, down to this fraction of the drawn ripening day.
RIPENING_SPEEDUP_PER_DEGREE: Final = 0.01
RIPENING_MIN_TIME_FACTOR: Final = 0.6
# Ripeness stages by progress towards the effective ripening day (1.0 is
# ripe). A ripe fruit becomes overripe this many days later.
IMMATURE_GREEN_FROM_PROGRESS: Final = 0.1
MATURE_GREEN_FROM_PROGRESS: Final = 0.4
TURNING_FROM_PROGRESS: Final = 0.85
OVERRIPE_AFTER_DAYS: Final = 8

# Water use rises by this share per degree above the reference temperature,
# and falls no lower than this fraction of the base rate below it.
WATER_USE_INCREASE_PER_DEGREE: Final = 0.03
WATER_USE_MIN_TEMPERATURE_FACTOR: Final = 0.3
# Water use rises by this share for each initial stem length the plant has
# grown to.
WATER_USE_INCREASE_PER_INITIAL_STEM_LENGTH: Final = 0.01
# Daily change in water stress (0 to 1) while the root zone is below the
# scenario's stress threshold, and while it is above it.
WATER_STRESS_RISE_PER_DAY: Final = 0.08
WATER_STRESS_RECOVERY_PER_DAY: Final = 0.05
