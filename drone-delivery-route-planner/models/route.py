"""Route: the result of a solver - the tour, its length, time and statistics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from models.location import Location

if TYPE_CHECKING:  # only needed for type hints, avoids a circular import
    from models.delivery_network import DeliveryNetwork


@dataclass
class Route:
    """A closed tour: start -> stops... -> start.

    Attributes:
        path: Locations in visiting order. First and last item are the start.
        total_distance: Tour length in km.
        estimated_time_minutes: Flight time at the drone's speed.
        algorithm: Name of the algorithm that produced the route.
        execution_time: Seconds the algorithm needed.
        stats: Extra numbers (e.g. Branch and Bound nodes explored).
    """

    path: List[Location]
    total_distance: float
    estimated_time_minutes: float
    algorithm: str
    execution_time: float = 0.0
    stats: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_indices(
        cls,
        network: "DeliveryNetwork",
        indices: Sequence[int],
        algorithm: str,
        execution_time: float = 0.0,
        stats: Optional[Dict[str, Any]] = None,
    ) -> "Route":
        """Build a Route from location indices such as [0, 2, 1, 3, 0].

        Raises ValueError if the tour is not a proper round trip that visits
        every delivery stop exactly once.
        """
        indices = list(indices)
        expected_stops = list(range(1, network.num_stops + 1))
        if (
            len(indices) != network.num_stops + 2
            or indices[0] != 0
            or indices[-1] != 0
            or sorted(indices[1:-1]) != expected_stops
        ):
            raise ValueError(
                "A route must start at 0, visit every stop exactly once and return to 0; "
                f"got {indices}."
            )
        distance = network.path_distance(indices)
        return cls(
            path=[network.locations[i] for i in indices],
            total_distance=distance,
            estimated_time_minutes=network.drone.travel_time_minutes(distance),
            algorithm=algorithm,
            execution_time=execution_time,
            stats=dict(stats or {}),
        )

    # --------------------------------------------------------------- read-outs
    @property
    def names(self) -> List[str]:
        return [loc.name for loc in self.path]

    @property
    def num_locations_visited(self) -> int:
        """Distinct locations visited, start included (the return leg is not double counted)."""
        return len(self.path) - 1

    @property
    def num_deliveries(self) -> int:
        return len(self.path) - 2

    def path_string(self) -> str:
        """Human readable tour, e.g. 'A -> B -> C -> A'."""
        return " -> ".join(self.names)

    def __str__(self) -> str:
        return f"{self.path_string()}  ({self.total_distance:.2f} km, {self.algorithm})"
