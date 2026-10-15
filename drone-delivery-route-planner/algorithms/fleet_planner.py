"""FleetPlanner: plan deliveries for SEVERAL drones that share one depot.

This extends the single-drone TSP solvers to the multi-drone case
(a simple Vehicle Routing Problem) in three steps:

1. **Split** - the "sweep" method. Sort orders by their angle around the depot
   and cut the circular list into ``k`` groups with (almost) equal sizes. The
   cut position is tried at several rotations and the cheapest split is kept.
2. **Route** - every group is its own TSP, solved with the existing solvers:
   Dynamic Programming (exact) for small groups, Nearest Neighbour + 2-opt
   with random restarts for bigger ones.
3. **Battery** - if a battery range is set, a route that is too long loses its
   biggest-detour orders; those orders are offered to the other drones and are
   reported as *unassigned* if nobody can reach them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from algorithms.approximation import ApproximationSolver
from algorithms.dynamic_programming import DynamicProgrammingSolver
from models.delivery_network import DeliveryNetwork
from models.drone import DEFAULT_SPEED_KMH, Drone
from models.location import Location
from models.route import Route
from utils.exceptions import InvalidInputError

EPS = 1e-9
EXACT_LIMIT = 12            # groups up to this size are solved optimally (DP)
MAX_SWEEP_CANDIDATES = 24   # how many cut positions the sweep tries
NEAR_LIMIT_FRACTION = 0.90  # warn when a route uses more than 90 % of the range


@dataclass
class DroneAssignment:
    """What one drone does."""

    drone_id: int
    route: Optional[Route] = None            # None = this drone is not needed
    range_km: Optional[float] = None

    @property
    def used(self) -> bool:
        return self.route is not None

    @property
    def stops(self) -> List[Location]:
        """Orders in the order the drone visits them (depot excluded)."""
        return self.route.path[1:-1] if self.route else []

    @property
    def order_names(self) -> List[str]:
        return [s.name for s in self.stops]

    @property
    def distance_km(self) -> float:
        return self.route.total_distance if self.route else 0.0

    @property
    def time_minutes(self) -> float:
        return self.route.estimated_time_minutes if self.route else 0.0

    @property
    def algorithm(self) -> str:
        return self.route.algorithm if self.route else "-"

    @property
    def range_used_percent(self) -> Optional[float]:
        if self.range_km is None or not self.used:
            return None
        return self.distance_km / self.range_km * 100.0


@dataclass
class FleetPlan:
    """Result of FleetPlanner.plan."""

    depot: Location
    assignments: List[DroneAssignment]
    unassigned: List[Location] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_orders(self) -> int:
        return sum(len(a.stops) for a in self.assignments) + len(self.unassigned)

    @property
    def assigned_orders(self) -> int:
        return sum(len(a.stops) for a in self.assignments)

    @property
    def used_assignments(self) -> List[DroneAssignment]:
        return [a for a in self.assignments if a.used]

    @property
    def drones_used(self) -> int:
        return len(self.used_assignments)

    @property
    def total_distance_km(self) -> float:
        return sum(a.distance_km for a in self.assignments)

    @property
    def longest_time_minutes(self) -> float:
        """When the last drone is back (all drones fly at the same time)."""
        return max((a.time_minutes for a in self.assignments), default=0.0)


class FleetPlanner:
    """Assign orders to drones and plan each drone's round trip."""

    def __init__(
        self,
        num_drones: int,
        speed_kmh: float = DEFAULT_SPEED_KMH,
        max_range_km: Optional[float] = None,
        exact_limit: int = EXACT_LIMIT,
        seed: int = 0,
    ) -> None:
        if isinstance(num_drones, bool) or not isinstance(num_drones, int) or num_drones < 1:
            raise InvalidInputError("Number of drones must be a whole number >= 1.")
        self.num_drones = num_drones
        self.drone = Drone("Drone", speed_kmh, max_range_km)   # validates speed and range
        self.exact_limit = exact_limit
        self.seed = seed

    # ------------------------------------------------------------------ public
    def plan(self, depot: Location, orders: Sequence[Location]) -> FleetPlan:
        orders = list(orders)
        if not orders:
            raise InvalidInputError("At least one delivery order is required.")
        names = [depot.name, *(o.name for o in orders)]
        if len({n.lower() for n in names}) != len(names):
            raise InvalidInputError("Order names must be unique and different from the depot name.")

        warnings: List[str] = []
        k = min(self.num_drones, len(orders))
        if k < self.num_drones:
            warnings.append(
                f"Only {k} of {self.num_drones} drones are needed for {len(orders)} order(s); "
                f"the rest stay at the depot."
            )

        groups = self._best_sweep_split(depot, orders, k)
        unassigned: List[Location] = []
        routes: List[Optional[Route]] = []

        if self.drone.max_range_km is None:
            routes = [self._solve_group(depot, g) for g in groups]
        else:
            groups, routes, unassigned = self._enforce_range(depot, groups, warnings)

        assignments: List[DroneAssignment] = []
        for i in range(self.num_drones):
            route = routes[i] if i < len(routes) else None
            assignments.append(DroneAssignment(i + 1, route, self.drone.max_range_km))

        self._add_battery_warnings(assignments, warnings)
        return FleetPlan(depot, assignments, unassigned, warnings)

    # ------------------------------------------------------ step 1: sweep split
    def _best_sweep_split(self, depot: Location, orders: List[Location], k: int) -> List[List[Location]]:
        """Angle-sorted, size-balanced split; the cheapest rotation wins."""
        by_angle = sorted(orders, key=lambda o: math.atan2(o.y - depot.y, o.x - depot.x))
        n = len(by_angle)
        if k == 1:
            return [by_angle]

        step = max(1, n // MAX_SWEEP_CANDIDATES)
        best_groups: List[List[Location]] = []
        best_cost = math.inf
        for offset in range(0, n, step):
            rotated = by_angle[offset:] + by_angle[:offset]
            groups = self._chunk_evenly(rotated, k)
            cost = sum(self._quick_distance(depot, g) for g in groups)
            if cost < best_cost - EPS:
                best_cost, best_groups = cost, groups
        return best_groups

    @staticmethod
    def _chunk_evenly(items: List[Location], k: int) -> List[List[Location]]:
        """Cut ``items`` into ``k`` consecutive chunks whose sizes differ by at most 1."""
        base, extra = divmod(len(items), k)
        chunks, pos = [], 0
        for i in range(k):
            size = base + (1 if i < extra else 0)
            chunks.append(items[pos : pos + size])
            pos += size
        return chunks

    # ----------------------------------------------------- step 2: route a group
    def _network(self, depot: Location, group: Sequence[Location]) -> DeliveryNetwork:
        return DeliveryNetwork(depot, list(group), self.drone)

    def _quick_distance(self, depot: Location, group: Sequence[Location]) -> float:
        """Fast (heuristic) tour length - only used to compare candidate splits."""
        return ApproximationSolver().solve(self._network(depot, group)).total_distance

    def _solve_group(self, depot: Location, group: Sequence[Location]) -> Route:
        """Best route for one drone: exact when small, multi-start heuristic otherwise."""
        network = self._network(depot, group)
        if len(group) <= self.exact_limit:
            return DynamicProgrammingSolver(max_stops=self.exact_limit).solve(network)
        return ApproximationSolver(restarts=20, seed=self.seed).solve(network)

    # --------------------------------------------------- step 3: battery limits
    def _enforce_range(
        self, depot: Location, groups: List[List[Location]], warnings: List[str]
    ) -> Tuple[List[List[Location]], List[Optional[Route]], List[Location]]:
        limit = self.drone.max_range_km
        assert limit is not None
        kept: List[List[Location]] = []
        routes: List[Optional[Route]] = []
        removed: List[Location] = []

        for group in groups:
            group = list(group)
            route = self._solve_group(depot, group)
            while group and route.total_distance > limit + EPS:
                worst = self._biggest_detour(route)           # the costliest order
                group.remove(worst)
                removed.append(worst)
                route = self._solve_group(depot, group) if group else None
            kept.append(group)
            routes.append(route)

        # Offer every removed order to the drones that still have spare range.
        unassigned: List[Location] = []
        for order in sorted(removed, key=lambda o: math.hypot(o.x - depot.x, o.y - depot.y)):
            best: Optional[Tuple[float, int, Route]] = None
            for i, group in enumerate(kept):
                candidate = self._solve_group(depot, group + [order])
                if candidate.total_distance <= limit + EPS:
                    extra = candidate.total_distance - (routes[i].total_distance if routes[i] else 0.0)
                    if best is None or extra < best[0]:
                        best = (extra, i, candidate)
            if best is None:
                unassigned.append(order)
                warnings.append(self._unassigned_reason(depot, order, limit))
            else:
                _, i, candidate = best
                kept[i].append(order)
                routes[i] = candidate
        return kept, routes, sorted(unassigned, key=lambda o: o.name)

    @staticmethod
    def _biggest_detour(route: Route) -> Location:
        """The order whose removal would shorten the route the most."""
        path = route.path
        best, best_saving = path[1], -math.inf
        for i in range(1, len(path) - 1):
            a, b, c = path[i - 1], path[i], path[i + 1]
            saving = a.distance_to(b) + b.distance_to(c) - a.distance_to(c)
            if saving > best_saving:
                best, best_saving = b, saving
        return best

    @staticmethod
    def _unassigned_reason(depot: Location, order: Location, limit: float) -> str:
        round_trip = 2 * depot.distance_to(order)
        if round_trip > limit + EPS:
            return (f"Order {order.name} is unassigned: a round trip to it needs {round_trip:.1f} km "
                    f"but the battery range is {limit:.1f} km.")
        return (f"Order {order.name} is unassigned: no drone has enough battery left "
                f"(range {limit:.1f} km) to add it.")

    def _add_battery_warnings(self, assignments: List[DroneAssignment], warnings: List[str]) -> None:
        for a in assignments:
            pct = a.range_used_percent
            if pct is not None and pct > NEAR_LIMIT_FRACTION * 100:
                warnings.append(
                    f"Drone {a.drone_id} uses {pct:.0f}% of its battery range "
                    f"({a.distance_km:.1f} of {a.range_km:.1f} km) - very little margin."
                )
