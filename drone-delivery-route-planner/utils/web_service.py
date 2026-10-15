"""Glue between the Flask form and the planner (no Flask imports - easy to test).

* parse_plan_form  -> validate what the user typed
* build_plan_view  -> generate orders, run FleetPlanner, prepare everything the page shows
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from algorithms.fleet_planner import FleetPlan, FleetPlanner
from models.drone import DEFAULT_SPEED_KMH
from models.location import Location
from utils.exceptions import InvalidInputError
from utils.geo import km_to_lat_lon, random_points_in_disc, validate_lat_lon
from utils.route_svg import DEPOT_COLOR, UNASSIGNED_COLOR, drone_color, render_plan_svg

MAX_ORDERS = 60
MAX_DRONES = 10
DEFAULT_DEPOT = "17.3850, 78.4867"       # Hyderabad
DEFAULT_RADIUS_KM = 8.0

#: What the form shows when the page is first opened.
DEFAULT_FORM: Dict[str, str] = {
    "orders": "10",
    "drones": "3",
    "depot": DEFAULT_DEPOT,
    "battery": "",
    "speed": f"{DEFAULT_SPEED_KMH:g}",
    "radius": f"{DEFAULT_RADIUS_KM:g}",
}


@dataclass
class PlanRequest:
    """Validated form values."""

    num_orders: int
    num_drones: int
    depot_lat: float
    depot_lon: float
    max_range_km: Optional[float]
    speed_kmh: float
    radius_km: float
    seed: Optional[int]


# ----------------------------------------------------------------- validation
def _to_int(text: str, label: str, low: int, high: int, errors: List[str]) -> Optional[int]:
    try:
        value = int(text.strip())
    except (ValueError, AttributeError):
        errors.append(f"{label} must be a whole number (for example 10).")
        return None
    if not low <= value <= high:
        errors.append(f"{label} must be between {low} and {high}.")
        return None
    return value


def _to_float(text: str, label: str, errors: List[str], minimum: float = 0.0,
              maximum: Optional[float] = None) -> Optional[float]:
    try:
        value = float(text.strip())
    except (ValueError, AttributeError):
        errors.append(f"{label} must be a number.")
        return None
    if value != value or value in (float("inf"), float("-inf")) or value <= minimum:
        errors.append(f"{label} must be greater than {minimum:g}.")
        return None
    if maximum is not None and value > maximum:
        errors.append(f"{label} must be at most {maximum:g}.")
        return None
    return value


def parse_plan_form(form: Mapping[str, str]) -> Tuple[Optional[PlanRequest], List[str]]:
    """Validate the form. Returns (request, []) or (None, list of error messages)."""
    errors: List[str] = []
    get = lambda key: (form.get(key) or "").strip()

    orders = _to_int(get("orders"), "Number of orders", 1, MAX_ORDERS, errors)
    drones = _to_int(get("drones"), "Number of drones", 1, MAX_DRONES, errors)

    lat = lon = None
    parts = get("depot").replace(";", ",").split(",") if get("depot") else []
    if len(parts) != 2:
        errors.append("Depot location must look like: 17.3850, 78.4867 (latitude, longitude).")
    else:
        try:
            lat, lon = float(parts[0]), float(parts[1])
            validate_lat_lon(lat, lon)
        except InvalidInputError as exc:             # out of range (must come first: it is a ValueError too)
            errors.append(str(exc))
            lat = lon = None
        except ValueError:
            errors.append("Depot latitude and longitude must be numbers.")
            lat = lon = None

    battery: Optional[float] = None
    if get("battery"):
        battery = _to_float(get("battery"), "Battery range", errors)
    speed = _to_float(get("speed") or f"{DEFAULT_SPEED_KMH:g}", "Drone speed", errors, maximum=300)
    radius = _to_float(get("radius") or f"{DEFAULT_RADIUS_KM:g}", "Delivery radius", errors, maximum=100)

    seed: Optional[int] = None
    if get("seed"):
        try:
            seed = int(get("seed"))
        except ValueError:
            errors.append("Random seed must be a whole number.")

    if errors:
        return None, errors
    assert None not in (orders, drones, lat, lon, speed, radius)
    return PlanRequest(orders, drones, lat, lon, battery, speed, radius, seed), []  # type: ignore[arg-type]


# --------------------------------------------------------------- building view
def generate_orders(count: int, radius_km: float, seed: int) -> List[Location]:
    """Random delivery orders ``"1".."count"`` spread around the depot (local km plane)."""
    rng = random.Random(seed)
    return [Location(str(i + 1), x, y) for i, (x, y) in enumerate(random_points_in_disc(count, radius_km, rng))]


def build_plan_view(request: PlanRequest) -> Dict[str, Any]:
    """Run the planner and return a dictionary the results template can display."""
    seed = request.seed if request.seed is not None else random.SystemRandom().randrange(1, 1_000_000)
    depot = Location("Depot", 0.0, 0.0)
    orders = generate_orders(request.num_orders, request.radius_km, seed)

    planner = FleetPlanner(request.num_drones, request.speed_kmh, request.max_range_km, seed=seed)
    plan: FleetPlan = planner.plan(depot, orders)

    def latlon(loc: Location) -> Tuple[float, float]:
        return km_to_lat_lon(loc.x, loc.y, request.depot_lat, request.depot_lon)

    owner = {s.name: a.drone_id for a in plan.assignments for s in a.stops}
    rows = []
    for a in plan.assignments:
        rows.append({
            "id": a.drone_id,
            "color": drone_color(a.drone_id),
            "used": a.used,
            "orders_sorted": ", ".join(sorted(a.order_names, key=int)) or "-",
            "route": " \u2192 ".join(["Depot", *a.order_names, "Depot"]) if a.used else "not needed",
            "distance": a.distance_km,
            "minutes": a.time_minutes,
            "algorithm": a.algorithm,
            "battery_pct": a.range_used_percent,
        })
    max_distance = max((r["distance"] for r in rows), default=0.0) or 1.0
    for r in rows:
        r["bar_pct"] = r["distance"] / max_distance * 100

    order_rows = []
    for o in sorted(orders, key=lambda loc: int(loc.name)):
        lat, lon = latlon(o)
        order_rows.append({
            "id": o.name, "lat": lat, "lon": lon,
            "drone": owner.get(o.name),
            "color": drone_color(owner[o.name]) if o.name in owner else UNASSIGNED_COLOR,
        })

    return {
        "plan": plan,
        "svg": render_plan_svg(plan),
        "rows": rows,
        "order_rows": order_rows,
        "unassigned": sorted((o.name for o in plan.unassigned), key=int),
        "warnings": plan.warnings,
        "seed": seed,
        "depot_lat": request.depot_lat,
        "depot_lon": request.depot_lon,
        "depot_color": DEPOT_COLOR,
        "speed": request.speed_kmh,
        "max_range": request.max_range_km,
        "radius": request.radius_km,
        "total_orders": plan.total_orders,
        "assigned_orders": plan.assigned_orders,
        "drones_used": plan.drones_used,
        "drones_requested": request.num_drones,
        "total_distance": plan.total_distance_km,
        "longest_minutes": plan.longest_time_minutes,
    }
