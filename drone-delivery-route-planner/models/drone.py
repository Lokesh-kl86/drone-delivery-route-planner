"""Drone: knows how fast it flies and converts distance into flight time."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from utils.exceptions import InvalidInputError

DEFAULT_SPEED_KMH = 30.0  # 30 km/h  ->  2 minutes per km


@dataclass(frozen=True)
class Drone:
    """A delivery drone flying at a constant speed (km/h).

    ``max_range_km`` is the battery range for one full round trip
    (None = unlimited, which is the default and what the CLI uses).
    """

    name: str = "Drone-1"
    speed_kmh: float = DEFAULT_SPEED_KMH
    max_range_km: Optional[float] = None

    def __post_init__(self) -> None:
        speed = self.speed_kmh
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or speed <= 0
        ):
            raise InvalidInputError(f"Drone speed must be a positive number, got {speed!r}.")
        rng = self.max_range_km
        if rng is not None and (
            isinstance(rng, bool)
            or not isinstance(rng, (int, float))
            or not math.isfinite(rng)
            or rng <= 0
        ):
            raise InvalidInputError(f"Battery range must be a positive number or None, got {rng!r}.")

    def can_fly(self, distance_km: float) -> bool:
        """True if a trip of ``distance_km`` fits inside the battery range."""
        return self.max_range_km is None or distance_km <= self.max_range_km + 1e-9

    def travel_time_hours(self, distance_km: float) -> float:
        """Hours needed to fly ``distance_km``."""
        if distance_km < 0:
            raise InvalidInputError("Distance cannot be negative.")
        return distance_km / self.speed_kmh

    def travel_time_minutes(self, distance_km: float) -> float:
        """Minutes needed to fly ``distance_km``."""
        return self.travel_time_hours(distance_km) * 60.0
