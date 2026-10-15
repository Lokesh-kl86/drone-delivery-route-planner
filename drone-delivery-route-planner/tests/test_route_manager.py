"""RouteManager: comparisons and multiprocessing."""
import pytest

from algorithms import (
    ApproximationSolver,
    BranchAndBoundSolver,
    DynamicProgrammingSolver,
    RouteManager,
)
from tests.helpers import example_network, random_network
from utils.benchmark import format_comparison_table
from utils.exceptions import InvalidInputError


def test_compare_sequential_runs_all_three_algorithms():
    result = RouteManager(example_network()).compare(parallel=False)
    assert [r.algorithm for r in result.routes][:2] == ["Dynamic Programming", "Branch and Bound"]
    assert len(result.routes) == 3 and not result.parallel
    exact = result.routes[0].total_distance
    assert all(r.total_distance >= exact - 1e-9 for r in result.routes)


def test_compare_in_parallel_gives_same_answers_as_sequential():
    net = random_network(9, seed=11)
    sequential = RouteManager(net).compare(parallel=False)
    parallel = RouteManager(net, processes=3).compare(parallel=True)
    assert [round(r.total_distance, 9) for r in sequential.routes] == [
        round(r.total_distance, 9) for r in parallel.routes
    ]
    assert parallel.wall_time > 0 and parallel.sequential_time > 0


def test_too_large_for_exact_solvers_are_skipped_not_failed():
    net = random_network(20, seed=3)
    result = RouteManager(net).compare(parallel=False)
    assert [r.algorithm for r in result.routes] == ["Approximation (Nearest Neighbor + 2-opt)"]
    assert set(result.skipped) == {"Dynamic Programming", "Branch and Bound"}


def test_best_route_prefers_shorter_then_faster():
    result = RouteManager(example_network()).compare(parallel=False)
    best = result.best_route
    assert best.total_distance == pytest.approx(min(r.total_distance for r in result.routes))


def test_parallel_multistart_is_valid_and_not_worse_than_greedy():
    net = random_network(40, seed=5)
    manager = RouteManager(net, processes=2)
    greedy = ApproximationSolver().solve(net)
    route = manager.solve_large_parallel(total_restarts=8, seed=1, parallel=True)
    assert route.total_distance <= greedy.total_distance + 1e-9
    assert sorted(route.names[1:-1]) == sorted(loc.name for loc in net.deliveries)
    assert route.stats["restarts"] == 8


def test_parallel_and_sequential_multistart_agree():
    net = random_network(30, seed=8)
    manager = RouteManager(net, processes=2)
    a = manager.solve_large_parallel(total_restarts=6, seed=3, parallel=False)
    b = manager.solve_large_parallel(total_restarts=6, seed=3, parallel=True)
    assert a.total_distance == pytest.approx(b.total_distance)


def test_solve_auto_picks_exact_for_small_and_heuristic_for_large():
    assert RouteManager(example_network()).solve_auto().algorithm == "Dynamic Programming"
    assert RouteManager(random_network(30, seed=1)).solve_auto().algorithm.startswith("Approximation")


def test_comparison_table_contains_every_algorithm():
    result = RouteManager(example_network()).compare(
        [DynamicProgrammingSolver(), BranchAndBoundSolver()], parallel=False
    )
    table = format_comparison_table(result.routes)
    assert "Algorithm" in table and "Distance" in table and "Execution Time" in table
    assert "Dynamic Programming" in table and "Branch and Bound" in table


def test_invalid_manager_settings():
    with pytest.raises(InvalidInputError):
        RouteManager(example_network(), processes=0)
    with pytest.raises(InvalidInputError):
        RouteManager(example_network()).solve_large_parallel(total_restarts=0)
