"""DeliveryNetwork: the start point, the delivery stops and the drone.

Indexing convention used by every algorithm
-------------------------------------------
* Location index 0 is always the START.
* Location indices 1..n are the delivery stops.
* "Stop number" s = location index - 1 (so stops are 0..n-1). Bit masks in
  the solvers use the stop number: bit s set  <=>  stop s already visited.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from models.drone import Drone
from models.location import Location
from utils.distance import build_distance_matrix, path_length
from utils.exceptions import InvalidInputError


class DeliveryNetwork:
    """Everything a solver needs to know about one delivery problem."""

    def __init__(
        self,
        start: Location,
        deliveries: Sequence[Location],
        drone: Optional[Drone] = None,
    ) -> None:
        if not isinstance(start, Location):
            raise InvalidInputError("The start point must be a Location.")
        deliveries = list(deliveries)
        if not deliveries:
            raise InvalidInputError("At least one delivery location is required.")
        if not all(isinstance(d, Location) for d in deliveries):
            raise InvalidInputError("Every delivery stop must be a Location.")

        names = [start.name, *(d.name for d in deliveries)]
        lowered = [n.lower() for n in names]
        duplicates = sorted({n for n in names if lowered.count(n.lower()) > 1})
        if duplicates:
            raise InvalidInputError(f"Location names must be unique. Duplicates: {duplicates}")

        self.drone: Drone = drone if drone is not None else Drone()
        self._locations: List[Location] = [start, *deliveries]
        self._distance_matrix: List[List[float]] = build_distance_matrix(self._locations)
        self._required_masks: List[int] = self._compute_required_masks()

    # ------------------------------------------------------------------ basics
    @property
    def start(self) -> Location:
        return self._locations[0]

    @property
    def deliveries(self) -> List[Location]:
        return self._locations[1:]

    @property
    def locations(self) -> List[Location]:
        """Start first, then every delivery stop."""
        return list(self._locations)

    @property
    def num_locations(self) -> int:
        """Total number of locations, including the start."""
        return len(self._locations)

    @property
    def num_stops(self) -> int:
        """Number of delivery stops (excluding the start)."""
        return len(self._locations) - 1

    @property
    def distance_matrix(self) -> List[List[float]]:
        return self._distance_matrix

    def distance(self, i: int, j: int) -> float:
        return self._distance_matrix[i][j]

    def path_distance(self, indices: Sequence[int]) -> float:
        """Length of the path visiting location ``indices`` in order."""
        return path_length(indices, self._distance_matrix)

    # -------------------------------------------------------------- priorities
    @property
    def has_priorities(self) -> bool:
        """True when the stops do not all share the same priority."""
        return len({d.priority for d in self.deliveries}) > 1

    def required_masks(self) -> List[int]:
        """For each stop number s: bit mask of the stops that MUST come before it.

        A stop may only be visited once every stop with a smaller priority
        number has been visited. With no priorities all masks are 0 (no rules).
        """
        return self._required_masks

    def _compute_required_masks(self) -> List[int]:
        stops = self._locations[1:]
        masks: List[int] = []
        for stop in stops:
            mask = 0
            for other_number, other in enumerate(stops):
                if other.priority < stop.priority:
                    mask |= 1 << other_number
            masks.append(mask)
        return masks

    def is_priority_valid(self, order: Sequence[int]) -> bool:
        """Check an order of location indices (1..n) respects the priorities."""
        priorities = [self._locations[i].priority for i in order]
        return all(a <= b for a, b in zip(priorities, priorities[1:]))
