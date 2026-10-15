"""Small helpers shared by the test files."""
from __future__ import annotations

import itertools
from typing import Optional

from models import DeliveryNetwork, Drone, Location
from utils.benchmark import random_network  # re-exported for convenience

__all__ = ["example_network", "random_network", "brute_force_optimum"]


def example_network(speed: float = 30.0) -> DeliveryNetwork:
    """The 5-location example from the project brief."""
    return DeliveryNetwork(
        Location("A", 0, 0),
        [Location("B", 2, 3), Location("C", 5, 2), Location("D", 6, 6), Location("E", 1, 5)],
        Drone(speed_kmh=speed),
    )


def brute_force_optimum(network: DeliveryNetwork) -> float:
    """Try every possible order (only for tiny networks) - the 'ground truth'."""
    best: Optional[float] = None
    for order in itertools.permutations(range(1, network.num_stops + 1)):
        if network.has_priorities and not network.is_priority_valid(order):
            continue
        length = network.path_distance([0, *order, 0])
        if best is None or length < best:
            best = length
    assert best is not None
    return best
