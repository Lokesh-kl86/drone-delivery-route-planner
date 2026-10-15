"""Fast heuristic for large problems: Nearest Neighbour + 2-opt.

1. Nearest Neighbour builds a tour greedily: always fly to the closest stop
   that has not been visited yet.
2. 2-opt then improves it: take two legs of the tour, and if reversing the
   part between them makes the tour shorter, keep the change. Repeat until no
   swap helps.
3. Optional random restarts: start from random tours and keep the best result.
   (RouteManager can spread the restarts over several CPU cores.)

This does NOT guarantee the optimal tour, but it runs in about O(n^2) per pass
and is usually within a few percent of the optimum.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from algorithms.base import TSPOptimizer
from models.delivery_network import DeliveryNetwork

EPSILON = 1e-12  # ignore improvements smaller than floating-point noise


def nearest_neighbor_order(network: DeliveryNetwork) -> List[int]:
    """Greedy tour: repeatedly visit the closest allowed, unvisited stop.

    Returns the stop location-indices (1..n) in visiting order. Stops whose
    higher-priority stops are still pending are not "allowed" yet.
    """
    n = network.num_stops
    dist = network.distance_matrix
    required = network.required_masks()

    visited_mask = 0
    current = 0                                   # start at the depot
    order: List[int] = []
    for _ in range(n):
        best_stop, best_distance = -1, float("inf")
        for stop in range(n):
            if visited_mask & (1 << stop):
                continue
            if visited_mask & required[stop] != required[stop]:
                continue
            d = dist[current][stop + 1]
            if d < best_distance:
                best_stop, best_distance = stop, d
        visited_mask |= 1 << best_stop
        current = best_stop + 1
        order.append(current)
    return order


def two_opt(order: List[int], network: DeliveryNetwork) -> List[int]:
    """Improve ``order`` by reversing segments while that shortens the tour."""
    dist = network.distance_matrix
    n = len(order)
    best = list(order)
    check_priorities = network.has_priorities

    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                a = 0 if i == 0 else best[i - 1]       # stop before the segment
                b, c = best[i], best[j]                # first / last stop inside it
                d = 0 if j == n - 1 else best[j + 1]   # stop after the segment
                # Replace edges (a,b) and (c,d) by (a,c) and (b,d):
                delta = dist[a][c] + dist[b][d] - dist[a][b] - dist[c][d]
                if delta < -EPSILON:
                    candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                    if check_priorities and not network.is_priority_valid(candidate):
                        continue                       # would break the delivery priorities
                    best = candidate
                    improved = True
    return best


def random_priority_order(network: DeliveryNetwork, rng: random.Random) -> List[int]:
    """Random tour that still respects priorities (shuffle inside each priority group)."""
    stops = list(range(1, network.num_stops + 1))
    rng.shuffle(stops)
    # sorted() is stable, so equal priorities keep their shuffled order.
    return sorted(stops, key=lambda s: network.locations[s].priority)


class ApproximationSolver(TSPOptimizer):
    """Nearest Neighbour + 2-opt, optionally with random restarts."""

    def __init__(
        self,
        restarts: int = 1,
        seed: Optional[int] = None,
        use_greedy_start: bool = True,
    ) -> None:
        """
        Args:
            restarts: How many starting tours to improve (1 = greedy only).
            seed: Random seed so results can be reproduced.
            use_greedy_start: Make the first attempt the Nearest Neighbour tour.
        """
        if restarts < 1:
            raise ValueError("restarts must be at least 1.")
        self.restarts = restarts
        self.seed = seed
        self.use_greedy_start = use_greedy_start
        self.name = (
            "Approximation (Nearest Neighbor + 2-opt)"
            if restarts == 1
            else f"Approximation (NN + 2-opt, {restarts} restarts)"
        )

    def _find_order(self, network: DeliveryNetwork) -> Tuple[List[int], Dict[str, Any]]:
        rng = random.Random(self.seed)
        best_order: List[int] = []
        best_cost = float("inf")

        for attempt in range(self.restarts):
            if attempt == 0 and self.use_greedy_start:
                start_order = nearest_neighbor_order(network)
            else:
                start_order = random_priority_order(network, rng)
            improved = two_opt(start_order, network)
            cost = network.path_distance([0, *improved, 0])
            if cost < best_cost:
                best_cost, best_order = cost, improved

        return best_order, {"restarts": self.restarts}
