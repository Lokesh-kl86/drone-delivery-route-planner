"""Distance calculations (Euclidean) used by the whole project."""
from __future__ import annotations

import math
from typing import List, Protocol, Sequence


class HasCoordinates(Protocol):
    """Anything with ``x`` and ``y`` (e.g. a Location) can be measured."""

    @property
    def x(self) -> float: ...

    @property
    def y(self) -> float: ...


def euclidean_distance(a: HasCoordinates, b: HasCoordinates) -> float:
    """Straight-line distance between two points: sqrt((x1-x2)^2 + (y1-y2)^2)."""
    return math.hypot(a.x - b.x, a.y - b.y)


def build_distance_matrix(points: Sequence[HasCoordinates]) -> List[List[float]]:
    """Pre-compute every pairwise distance once.

    ``matrix[i][j]`` is the distance from point i to point j. The matrix is
    symmetric, so we only compute half of it and mirror the value.
    """
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            matrix[i][j] = matrix[j][i] = euclidean_distance(points[i], points[j])
    return matrix


def path_length(indices: Sequence[int], matrix: Sequence[Sequence[float]]) -> float:
    """Total length of a path that visits ``indices`` in the given order."""
    return sum(matrix[a][b] for a, b in zip(indices, indices[1:]))
