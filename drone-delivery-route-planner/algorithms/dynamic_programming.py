"""Exact TSP with Dynamic Programming (the Held-Karp algorithm).

Idea
----
Let ``dp[mask][last]`` be the shortest distance that starts at the depot,
visits exactly the stops in ``mask`` and ends at stop ``last``.

    dp[{j}][j]                = dist(start, j)
    dp[mask + nxt][nxt]       = min over last of  dp[mask][last] + dist(last, nxt)
    answer                    = min over last of  dp[all][last] + dist(last, start)

Because every sub-problem (mask, last) is solved only once, the running time
is O(n^2 * 2^n) instead of the O(n!) of brute force.

Priorities: a stop may join ``mask`` only if all stops with a smaller priority
number are already in it (see DeliveryNetwork.required_masks).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from algorithms.base import TSPOptimizer
from models.delivery_network import DeliveryNetwork

#: 2^15 * 15 = about 490,000 states - still fast enough in pure Python.
DEFAULT_MAX_STOPS = 15


class DynamicProgrammingSolver(TSPOptimizer):
    """Optimal route for small numbers of delivery stops."""

    name = "Dynamic Programming"

    def __init__(self, max_stops: int = DEFAULT_MAX_STOPS) -> None:
        if max_stops < 1:
            raise ValueError("max_stops must be at least 1.")
        self.max_stops = max_stops

    def _find_order(self, network: DeliveryNetwork) -> Tuple[List[int], Dict[str, Any]]:
        n = network.num_stops
        dist = network.distance_matrix          # index 0 = start, 1..n = stops
        required = network.required_masks()     # indexed by stop number 0..n-1
        full_mask = (1 << n) - 1

        # dp[mask][last] = best distance; parent[mask][last] = stop visited before `last`
        dp = [[math.inf] * n for _ in range(1 << n)]
        parent = [[-1] * n for _ in range(1 << n)]

        # Base case: fly from the start straight to one stop (if priorities allow it).
        for stop in range(n):
            if required[stop] == 0:
                dp[1 << stop][stop] = dist[0][stop + 1]

        # Masks are processed in increasing order, so every mask is final before we use it.
        for mask in range(1, full_mask + 1):
            for last in range(n):
                current = dp[mask][last]
                if current == math.inf:
                    continue                                   # unreachable state
                for nxt in range(n):
                    if mask & (1 << nxt):
                        continue                               # already visited
                    if mask & required[nxt] != required[nxt]:
                        continue                               # higher-priority stop still pending
                    new_mask = mask | (1 << nxt)
                    cost = current + dist[last + 1][nxt + 1]
                    if cost < dp[new_mask][nxt]:
                        dp[new_mask][nxt] = cost
                        parent[new_mask][nxt] = last

        # Close the loop: return to the start from the best final stop.
        best_cost, best_last = math.inf, -1
        for last in range(n):
            cost = dp[full_mask][last] + dist[last + 1][0]
            if cost < best_cost:
                best_cost, best_last = cost, last

        # Walk the parent pointers backwards to rebuild the order.
        order: List[int] = []
        mask, last = full_mask, best_last
        while last != -1:
            order.append(last + 1)                             # stop number -> location index
            previous = parent[mask][last]
            mask ^= 1 << last
            last = previous
        order.reverse()

        return order, {"dp_states": n * (1 << n)}
