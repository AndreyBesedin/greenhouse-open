"""The units the simulator's parts count in, and the constants of nature
more than one of them uses, each defined once (audit W13, `AUDIT.9`), so
that no two parts give one quantity two names or two values.

A value that only one part uses stays with that part. A run counts time in
seconds and angles in degrees, as the simulator's interfaces do. This
module imports nothing from the simulator, so any part may use it.
"""

from typing import Final

# Time, in seconds, and an hour's share of a day.
HOUR_S: Final = 3600.0
DAY_S: Final = 86_400.0
HOURS_A_DAY: Final = 24
# A mean year, in days, as the earth's orbit and the seasons go round it.
DAYS_IN_A_YEAR: Final = 365.25

# Turns, in degrees.
QUARTER_TURN_DEG: Final = 90.0
HALF_TURN_DEG: Final = 180.0
FULL_TURN_DEG: Final = 360.0

# A centimetre, in metres; a whole, in percent.
METRES_PER_CENTIMETRE: Final = 0.01
PERCENT: Final = 100.0

# The air's density at a greenhouse's temperatures, in kg/m³: what turns the
# air's volume into its mass, and a solver's kinematic pressure into pascals.
AIR_DENSITY_KG_M3: Final = 1.2
