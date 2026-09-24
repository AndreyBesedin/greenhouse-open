import zlib

import numpy as np


def stable_int(value: str) -> int:
    """Deterministic string -> int, unlike Python's per-process-randomized hash()."""
    return zlib.crc32(value.encode())


def seeded_rng(*entropy: int | str) -> np.random.Generator:
    ints = [stable_int(e) if isinstance(e, str) else e for e in entropy]
    return np.random.default_rng(np.random.SeedSequence(ints))
