"""Growth curves the organ model shares."""

from typing import Final

# The smoothstep curve, 3p² - 2p³: flat at both ends, steepest halfway.
SMOOTHSTEP_SQUARE: Final = 3
SMOOTHSTEP_CUBE: Final = 2


def smoothstep(progress: float) -> float:
    """A smooth S-curve from 0 to 1 as `progress` runs from 0 to 1: slow at
    first, fastest halfway, slow again at the end; 0 before, 1 after."""
    held = min(1.0, max(0.0, progress))
    return held * held * (SMOOTHSTEP_SQUARE - SMOOTHSTEP_CUBE * held)
