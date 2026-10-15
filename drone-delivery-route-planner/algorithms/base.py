"""TSPOptimizer: the abstract parent of every solver.

A solver only has to implement ``_find_order``. The shared ``solve`` method
does the boring parts: size check, timing and building the Route object.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from models.delivery_network import DeliveryNetwork
from models.route import Route
from utils.exceptions import ProblemTooLargeError


class TSPOptimizer(ABC):
    """Common interface for all route optimisation algorithms."""

    #: Name shown in reports and tables (subclasses override it).
    name: str = "TSP Optimizer"
    #: Largest number of delivery stops this solver accepts (None = no limit).
    max_stops: Optional[int] = None

    def supports(self, network: DeliveryNetwork) -> bool:
        """Can this solver handle the network's size?"""
        return self.max_stops is None or network.num_stops <= self.max_stops

    def solve(self, network: DeliveryNetwork) -> Route:
        """Find a tour, time it, and return it as a Route."""
        if not self.supports(network):
            raise ProblemTooLargeError(
                f"{self.name} supports at most {self.max_stops} delivery stops "
                f"but the network has {network.num_stops}."
            )
        started = time.perf_counter()
        order, stats = self._find_order(network)
        elapsed = time.perf_counter() - started
        return Route.from_indices(network, [0, *order, 0], self.name, elapsed, stats)

    @abstractmethod
    def _find_order(self, network: DeliveryNetwork) -> Tuple[List[int], Dict[str, Any]]:
        """Return (order of stop location-indices 1..n, extra statistics)."""
