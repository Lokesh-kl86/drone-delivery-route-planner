"""Nearest Neighbour + 2-opt approximation."""
import pytest

from algorithms import ApproximationSolver, DynamicProgrammingSolver
from algorithms.approximation import nearest_neighbor_order, two_opt
from tests.helpers import example_network, random_network


def test_route_is_a_valid_round_trip():
    net = random_network(25, seed=4)
    route = ApproximationSolver().solve(net)
    assert route.path[0] == net.start and route.path[-1] == net.start
    assert sorted(route.names[1:-1]) == sorted(loc.name for loc in net.deliveries)


def test_never_better_than_optimal_and_reasonably_close():
    for seed in range(8):
        net = random_network(9, seed=seed)
        optimal = DynamicProgrammingSolver().solve(net).total_distance
        approx = ApproximationSolver().solve(net).total_distance
        assert approx >= optimal - 1e-9
        assert approx <= optimal * 1.25        # 2-opt is usually within a few percent


def test_two_opt_never_makes_the_tour_longer():
    for seed in range(8):
        net = random_network(15, seed=seed)
        greedy = nearest_neighbor_order(net)
        improved = two_opt(greedy, net)
        assert net.path_distance([0, *improved, 0]) <= net.path_distance([0, *greedy, 0]) + 1e-9
        assert sorted(improved) == sorted(greedy)


def test_nearest_neighbor_starts_with_the_closest_stop():
    net = example_network()
    order = nearest_neighbor_order(net)
    assert order[0] == 1                      # B(2,3) is the closest stop to A(0,0)


def test_restarts_are_reproducible_with_a_seed():
    net = random_network(20, seed=2)
    first = ApproximationSolver(restarts=8, seed=5).solve(net)
    second = ApproximationSolver(restarts=8, seed=5).solve(net)
    assert first.names == second.names


def test_restarts_never_hurt_when_greedy_start_is_kept():
    net = random_network(30, seed=9)
    single = ApproximationSolver().solve(net).total_distance
    multi = ApproximationSolver(restarts=10, seed=1).solve(net).total_distance
    assert multi <= single + 1e-9


def test_respects_priorities():
    for seed in range(6):
        net = random_network(20, seed=seed, num_priority_levels=3)
        for solver in (ApproximationSolver(), ApproximationSolver(restarts=5, seed=seed)):
            priorities = [loc.priority for loc in solver.solve(net).path[1:-1]]
            assert priorities == sorted(priorities)


def test_invalid_restarts():
    with pytest.raises(ValueError):
        ApproximationSolver(restarts=0)
