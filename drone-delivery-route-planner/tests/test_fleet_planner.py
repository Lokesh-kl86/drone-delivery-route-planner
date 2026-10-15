"""Multi-drone planning: splitting, routing and battery limits."""
import random

import pytest

from algorithms import DynamicProgrammingSolver
from algorithms.fleet_planner import FleetPlanner
from models import DeliveryNetwork, Drone, Location
from utils.exceptions import InvalidInputError
from utils.geo import random_points_in_disc

DEPOT = Location("Depot", 0, 0)


def make_orders(count, seed=1, radius=8.0):
    rng = random.Random(seed)
    return [Location(str(i + 1), x, y) for i, (x, y) in enumerate(random_points_in_disc(count, radius, rng))]


def delivered(plan):
    return sorted(name for a in plan.assignments for name in a.order_names)


def test_every_order_is_delivered_exactly_once():
    for n, k in [(1, 1), (5, 2), (10, 3), (17, 4), (30, 5)]:
        orders = make_orders(n, seed=n)
        plan = FleetPlanner(k).plan(DEPOT, orders)
        assert delivered(plan) == sorted(o.name for o in orders)
        assert plan.unassigned == []
        assert plan.total_orders == n


def test_orders_are_shared_evenly():
    plan = FleetPlanner(3).plan(DEPOT, make_orders(10))
    sizes = sorted(len(a.stops) for a in plan.assignments)
    assert sizes == [3, 3, 4]                       # like the 4 / 3 / 3 split in the design


def test_one_drone_matches_the_single_drone_optimum():
    orders = make_orders(8, seed=3)
    plan = FleetPlanner(1).plan(DEPOT, orders)
    optimal = DynamicProgrammingSolver().solve(DeliveryNetwork(DEPOT, orders)).total_distance
    assert plan.total_distance_km == pytest.approx(optimal)


def test_two_separate_clusters_go_to_two_drones():
    east = [Location("1", 10, 1), Location("2", 11, -1)]
    west = [Location("3", -10, 1), Location("4", -11, -1)]
    plan = FleetPlanner(2).plan(DEPOT, east + west)
    groups = sorted(sorted(a.order_names) for a in plan.assignments)
    assert groups == [["1", "2"], ["3", "4"]]


def test_routes_are_round_trips_from_the_depot():
    plan = FleetPlanner(3).plan(DEPOT, make_orders(10))
    for a in plan.used_assignments:
        assert a.route.path[0] == DEPOT and a.route.path[-1] == DEPOT
        assert a.distance_km == pytest.approx(a.route.total_distance)
        assert a.time_minutes == pytest.approx(a.distance_km / 30 * 60)


def test_more_drones_than_orders_leaves_extra_drones_idle():
    plan = FleetPlanner(5).plan(DEPOT, make_orders(2))
    assert plan.drones_used == 2 and len(plan.assignments) == 5
    assert any("Only 2 of 5 drones" in w for w in plan.warnings)
    assert all(not a.used for a in plan.assignments[2:])


def test_small_groups_are_solved_exactly_and_large_ones_by_heuristic():
    small = FleetPlanner(2).plan(DEPOT, make_orders(10))
    assert all(a.algorithm == "Dynamic Programming" for a in small.used_assignments)
    large = FleetPlanner(1).plan(DEPOT, make_orders(20))
    assert large.used_assignments[0].algorithm.startswith("Approximation")


def test_same_input_gives_the_same_plan():
    orders = make_orders(14, seed=5)
    a = FleetPlanner(3, seed=1).plan(DEPOT, orders)
    b = FleetPlanner(3, seed=1).plan(DEPOT, orders)
    assert [x.order_names for x in a.assignments] == [x.order_names for x in b.assignments]


# ------------------------------------------------------------------ battery
def test_generous_battery_changes_nothing():
    orders = make_orders(10)
    free = FleetPlanner(3).plan(DEPOT, orders)
    limited = FleetPlanner(3, max_range_km=500).plan(DEPOT, orders)
    assert limited.unassigned == []
    assert limited.total_distance_km == pytest.approx(free.total_distance_km)


def test_routes_never_exceed_the_battery_range():
    for limit in (12, 15, 20, 25):
        plan = FleetPlanner(3, max_range_km=limit).plan(DEPOT, make_orders(10, seed=4))
        for a in plan.used_assignments:
            assert a.distance_km <= limit + 1e-9
        assert plan.assigned_orders + len(plan.unassigned) == 10
        assert len(delivered(plan)) == plan.assigned_orders


def test_order_that_is_too_far_is_reported_unassigned():
    orders = [Location("1", 1, 0), Location("2", 2, 0), Location("3", 50, 0)]
    plan = FleetPlanner(2, max_range_km=10).plan(DEPOT, orders)
    assert [o.name for o in plan.unassigned] == ["3"]
    assert any("Order 3 is unassigned" in w and "round trip" in w for w in plan.warnings)
    assert delivered(plan) == ["1", "2"]


def test_tiny_battery_assigns_nothing_but_does_not_crash():
    plan = FleetPlanner(2, max_range_km=0.5).plan(DEPOT, make_orders(4))
    assert plan.drones_used == 0 and plan.total_distance_km == 0.0
    assert len(plan.unassigned) == 4


def test_orders_are_moved_to_a_drone_with_spare_battery():
    # one drone would be overloaded by the 4 orders, but 2 drones can share them
    orders = [Location("1", 3, 0), Location("2", 3, 1), Location("3", -3, 0), Location("4", -3, 1)]
    one = FleetPlanner(1, max_range_km=9).plan(DEPOT, orders)
    two = FleetPlanner(2, max_range_km=9).plan(DEPOT, orders)
    assert len(one.unassigned) > 0
    assert two.unassigned == []


def test_battery_usage_warning_near_the_limit():
    orders = [Location("1", 5, 0)]            # round trip = 10 km
    plan = FleetPlanner(1, max_range_km=10.2).plan(DEPOT, orders)
    assert plan.assignments[0].range_used_percent == pytest.approx(10 / 10.2 * 100)
    assert any("Drone 1 uses" in w for w in plan.warnings)


# ----------------------------------------------------------------- validation
def test_invalid_inputs():
    with pytest.raises(InvalidInputError):
        FleetPlanner(0)
    with pytest.raises(InvalidInputError):
        FleetPlanner(2, speed_kmh=-1)
    with pytest.raises(InvalidInputError):
        FleetPlanner(2, max_range_km=0)
    with pytest.raises(InvalidInputError):
        FleetPlanner(2).plan(DEPOT, [])
    with pytest.raises(InvalidInputError):
        FleetPlanner(2).plan(DEPOT, [Location("1", 1, 1), Location("1", 2, 2)])


def test_drone_battery_helpers():
    assert Drone().can_fly(10_000)                 # default: unlimited
    d = Drone(max_range_km=12)
    assert d.can_fly(12) and not d.can_fly(12.5)
    for bad in (0, -1, float("nan"), "far"):
        with pytest.raises(InvalidInputError):
            Drone(max_range_km=bad)
