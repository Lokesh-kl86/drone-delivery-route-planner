"""Branch and Bound solver."""
import math

import pytest

from algorithms import BranchAndBoundSolver, DynamicProgrammingSolver
from tests.helpers import brute_force_optimum, example_network, random_network
from utils.exceptions import ProblemTooLargeError


def test_example_matches_dynamic_programming():
    net = example_network()
    bnb = BranchAndBoundSolver().solve(net)
    dp = DynamicProgrammingSolver().solve(net)
    assert bnb.total_distance == pytest.approx(dp.total_distance)
    assert bnb.algorithm == "Branch and Bound"


def test_matches_brute_force_on_random_networks():
    for n in range(1, 8):
        for seed in range(6):
            net = random_network(n, seed=seed * 17 + n)
            assert BranchAndBoundSolver().solve(net).total_distance == pytest.approx(
                brute_force_optimum(net)
            )


def test_matches_dp_on_medium_networks():
    for seed in range(3):
        net = random_network(10, seed=seed)
        assert BranchAndBoundSolver().solve(net).total_distance == pytest.approx(
            DynamicProgrammingSolver().solve(net).total_distance
        )


def test_prunes_most_of_the_search_space():
    net = random_network(9, seed=3)
    stats = BranchAndBoundSolver().solve(net).stats
    # Brute force would expand every partial tour: sum of 9!/(9-k)! for k = 0..9.
    full_tree = sum(math.factorial(9) // math.factorial(9 - k) for k in range(10))
    assert stats["nodes_pruned"] > 0
    assert stats["nodes_explored"] < full_tree / 10


def test_respects_priorities():
    for seed in range(6):
        net = random_network(6, seed=seed, num_priority_levels=3)
        route = BranchAndBoundSolver().solve(net)
        priorities = [loc.priority for loc in route.path[1:-1]]
        assert priorities == sorted(priorities)
        assert route.total_distance == pytest.approx(brute_force_optimum(net))


def test_too_many_stops_raises():
    net = random_network(6, seed=1)
    with pytest.raises(ProblemTooLargeError):
        BranchAndBoundSolver(max_stops=5).solve(net)
