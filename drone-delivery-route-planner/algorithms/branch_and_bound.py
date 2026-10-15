"""Exact TSP with Branch and Bound.

Idea
----
Build the tour one stop at a time (this is "branching"). For every partial
tour compute a LOWER BOUND on the length of any full tour that starts with it.
If that bound is already >= the best complete tour found so far, the whole
branch is hopeless and is skipped ("bounding"). That avoids most of the n!
possible tours.

Lower bound used (cheap but always valid)
-----------------------------------------
Every remaining location (the current one plus all unvisited ones) must be
left exactly once, and the edge it is left by must lead to an unvisited stop
or back to the start. So the rest of the tour costs at least the sum, over
those locations, of the cheapest such edge:

    bound = distance_so_far + sum(cheapest allowed edge out of x
                                  for x in {current} + unvisited)

Two tricks make pruning effective:
* The search starts with an upper bound from the Nearest Neighbour heuristic.
* The closest candidate stop is tried first, so good tours are found early.

Priorities: a stop may only be chosen once all higher-priority stops are done.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from algorithms.approximation import nearest_neighbor_order
from algorithms.base import TSPOptimizer
from models.delivery_network import DeliveryNetwork

EPSILON = 1e-12
DEFAULT_MAX_STOPS = 15   # B&B is exponential in the worst case; raise with care


class BranchAndBoundSolver(TSPOptimizer):
    """Optimal route found by depth-first search with pruning."""

    name = "Branch and Bound"

    def __init__(self, max_stops: int = DEFAULT_MAX_STOPS) -> None:
        if max_stops < 1:
            raise ValueError("max_stops must be at least 1.")
        self.max_stops = max_stops

    def _find_order(self, network: DeliveryNetwork) -> Tuple[List[int], Dict[str, Any]]:
        n = network.num_stops
        dist = network.distance_matrix
        required = network.required_masks()

        # For every location: the other locations sorted by distance (nearest first).
        neighbours = [
            sorted((j for j in range(n + 1) if j != i), key=lambda j, i=i: dist[i][j])
            for i in range(n + 1)
        ]

        def lower_bound_rest(location: int, visited: int) -> float:
            """Cheapest conceivable cost of finishing the tour from ``location``.

            Sum of the cheapest allowed outgoing edge of ``location`` and of every
            unvisited stop. "Allowed" = leads to an unvisited stop or the start.
            """
            total = 0.0
            for node in [location, *(s + 1 for s in range(n) if not visited & (1 << s))]:
                for other in neighbours[node]:
                    if other == 0 or not visited & (1 << (other - 1)):
                        if other != node:
                            total += dist[node][other]
                            break
            return total

        # Initial upper bound: a quick greedy tour. It is also the fallback answer.
        best_order = nearest_neighbor_order(network)
        best_cost = network.path_distance([0, *best_order, 0])
        initial_bound = best_cost

        explored = 0      # partial tours we expanded
        pruned = 0        # branches cut off by the bound
        path: List[int] = []

        def branch(last: int, visited: int, cost: float) -> None:
            """Extend the partial tour ``path`` (currently at location ``last``)."""
            nonlocal best_cost, best_order, explored, pruned
            explored += 1

            if len(path) == n:                               # every stop visited
                total = cost + dist[last][0]                 # fly home
                if total < best_cost - EPSILON:
                    best_cost, best_order = total, path.copy()
                return

            candidates = [
                stop
                for stop in range(n)
                if not visited & (1 << stop) and visited & required[stop] == required[stop]
            ]
            candidates.sort(key=lambda stop: dist[last][stop + 1])   # nearest first

            for stop in candidates:
                location = stop + 1
                new_cost = cost + dist[last][location]
                new_visited = visited | (1 << stop)
                # Bound: what we have flown + the cheapest possible way to finish.
                if new_cost + lower_bound_rest(location, new_visited) >= best_cost - EPSILON:
                    pruned += 1
                    continue
                path.append(location)
                branch(location, new_visited, new_cost)
                path.pop()

        branch(0, 0, 0.0)

        stats = {
            "nodes_explored": explored,
            "nodes_pruned": pruned,
            "initial_upper_bound": round(initial_bound, 6),
        }
        return best_order, stats
