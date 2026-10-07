"""Where the organ model's randomness comes from: one seed, and a hierarchy
of identifiers under it.

There is one seed, the simulation's. Every draw is made from a generator
derived from that seed and a hash of who draws and what for: the plant,
then, for an organ's own draws, the organ, then the process the draw is for:

    simulation seed → plant → organ → process

so a plant's draws never depend on which other plants exist, an organ's on
which other organs do, or one process's on another's. Adding a plant, an
organ or a kind of draw changes nothing that was drawn before. What is
hashed is an identifier, which never changes, not an organ's state, which
does as it grows: a draw keyed by state would change with it.
"""

import numpy as np

from greenhouse_sim.core.rng import seeded_rng


def plant_rng(seed: int, plant_id: str, process: str) -> np.random.Generator:
    """The generator for one of a plant's own processes, such as its vigour."""
    return seeded_rng(seed, plant_id, "plant", process)


def organ_rng(seed: int, plant_id: str, organ_id: str, process: str) -> np.random.Generator:
    """The generator for one of an organ's own processes, such as whether a
    flower sets fruit."""
    return seeded_rng(seed, plant_id, "organ", organ_id, process)
