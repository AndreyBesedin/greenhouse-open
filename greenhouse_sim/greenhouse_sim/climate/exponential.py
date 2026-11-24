"""The exponential of a small square matrix, by scaling and squaring a Padé
approximant (Moler and Van Loan 2003, "Nineteen dubious ways to compute the
exponential of a matrix, twenty-five years later", SIAM Review 45(1), 3-49,
method 3; Golub and Van Loan, *Matrix Computations*, the scaling and
squaring algorithm).

The matrix is halved until its 1-norm is at most `SCALED_NORM`, its
exponential there approximated by the diagonal [6/6] Padé approximant, and
the result squared back as often as it was halved. At that norm the
approximant's relative error is at most 2^(3 - 2q) (q!)^2 / ((2q)! (2q + 1)!),
3.4e-16 for q = 6 (Golub and Van Loan), so the exponential is as exact as
the squarings' rounding allows, for the few nodes a house's climate has.
"""

import math
from typing import Final

import numpy as np

# The 1-norm the matrix is halved to before its approximant is taken.
SCALED_NORM: Final = 0.5
# The [6/6] Padé approximant's coefficients, c_k = (12 - k)! 6! / (12! k! (6 - k)!).
_PADE_6: Final = tuple(
    math.factorial(12 - k)
    * math.factorial(6)
    / (math.factorial(12) * math.factorial(k) * math.factorial(6 - k))
    for k in range(7)
)


def matrix_exponential(matrix: np.ndarray) -> np.ndarray:
    """e to the power of a square `matrix`, `exp(A) = Σ Aᵏ / k!`: see the
    module."""
    norm = float(np.abs(matrix).sum(axis=0).max()) if matrix.size else 0.0
    halvings = max(0, math.ceil(math.log2(norm / SCALED_NORM))) if norm > SCALED_NORM else 0
    scaled = matrix / 2.0**halvings
    identity = np.eye(matrix.shape[0])
    squared = scaled @ scaled
    fourth = squared @ squared
    sixth = fourth @ squared
    even = _PADE_6[0] * identity + _PADE_6[2] * squared + _PADE_6[4] * fourth + _PADE_6[6] * sixth
    odd = scaled @ (_PADE_6[1] * identity + _PADE_6[3] * squared + _PADE_6[5] * fourth)
    exponential: np.ndarray = np.linalg.solve(even - odd, even + odd)
    for _ in range(halvings):
        exponential = exponential @ exponential
    return exponential
