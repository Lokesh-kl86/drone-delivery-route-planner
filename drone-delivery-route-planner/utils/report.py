"""Formatting of the final route report shown in the terminal."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from models.delivery_network import DeliveryNetwork
from models.route import Route

WIDTH = 50


def format_route_report(route: Route, network: DeliveryNetwork) -> str:
    """Build the 'DRONE DELIVERY ROUTE PLANNER' result box."""
    lines: List[str] = [
        " DRONE DELIVERY ROUTE PLANNER ".center(WIDTH, "="),
        "",
        f"Locations: {network.num_locations}  (1 start + {network.num_stops} deliveries)",
        f"Drone: {network.drone.name} at {network.drone.speed_kmh:g} km/h",
    ]
    if network.has_priorities:
        groups: Dict[int, List[str]] = defaultdict(list)
        for loc in network.deliveries:
            groups[loc.priority].append(loc.name)
        lines.append("Priorities: " + "; ".join(
            f"P{p}: {', '.join(names)}" for p, names in sorted(groups.items())))
    lines += [
        "",
        "Best Route",
        f"  {route.path_string()}",
        "",
        f"Total Distance    : {route.total_distance:.2f} km",
        f"Estimated Time    : {route.estimated_time_minutes:.2f} minutes",
        f"Locations Visited : {route.num_locations_visited}",
        f"Algorithm         : {route.algorithm}",
        f"Execution Time    : {route.execution_time:.3f} seconds",
        "",
        "=" * WIDTH,
    ]
    return "\n".join(lines)
