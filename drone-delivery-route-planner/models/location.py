"""Location: a named point on a 2D map (coordinates are in kilometres)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from utils.distance import euclidean_distance
from utils.exceptions import InvalidInputError


def _is_real_number(value: object) -> bool:
    """True for finite ints/floats (booleans, strings, NaN and inf are rejected)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


@dataclass(frozen=True)
class Location:
    """A delivery stop (or the drone's start point).

    Attributes:
        name: Short label such as "A" or "Warehouse".
        x, y: Coordinates in kilometres.
        priority: 1 = most urgent. Stops with a smaller priority number are
            always delivered before stops with a larger one. Default is 1, so
            if nobody sets priorities the drone is free to pick any order.
    """

    name: str
    x: float
    y: float
    priority: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidInputError("A location needs a non-empty name.")
        if not (_is_real_number(self.x) and _is_real_number(self.y)):
            raise InvalidInputError(
                f"Coordinates of '{self.name}' must be finite numbers, "
                f"got ({self.x!r}, {self.y!r})."
            )
        if (
            isinstance(self.priority, bool)
            or not isinstance(self.priority, int)
            or self.priority < 1
        ):
            raise InvalidInputError(
                f"Priority of '{self.name}' must be a whole number >= 1, got {self.priority!r}."
            )

    @property
    def coordinates(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def distance_to(self, other: "Location") -> float:
        """Euclidean distance (km) from this location to ``other``."""
        return euclidean_distance(self, other)

    def __str__(self) -> str:
        return f"{self.name}({self.x:g}, {self.y:g})"
