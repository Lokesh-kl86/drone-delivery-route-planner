"""Dynamic Programming (Held-Karp) solver."""
import pytest

from algorithms import DynamicProgrammingSolver
from models import DeliveryNetwork, Location
from tests.helpers import brute_force_optimum, example_network, random_network
from utils.exceptions import ProblemTooLargeError


def test_known_square_has_perimeter_length():
    net = DeliveryNetwork(Location("S", 0, 0), [Location("P", 0, 1), Location("Q", 1, 1), Location("R", 1, 0)])
    assert DynamicProgrammingSolver().solve(net).total_distance == pytest.approx(4.0)


def test_points_on_a_line():
    net = DeliveryNetwork(Location("S", 0, 0), [Location("P", 1, 0), Location("Q", 2, 0), Location("R", 3, 0)])
    assert DynamicProgrammingSolver().solve(net).total_distance == pytest.approx(6.0)


def test_single_stop_goes_there_and_back():
    net = DeliveryNetwork(Location("S", 0, 0), [Location("P", 3, 4)])
    route = DynamicProgrammingSolver().solve(net)
    assert route.path_string() == "S -> P -> S"
    assert route.total_distance == pytest.approx(10.0)


def test_example_from_brief():
    route = DynamicProgrammingSolver().solve(example_network())
    assert route.total_distance == pytest.approx(20.449, abs=1e-3)
    assert route.algorithm == "Dynamic Programming"


def test_route_is_a_valid_round_trip():
    net = example_network()
    route = DynamicProgrammingSolver().solve(net)
    assert route.path[0] == net.start and route.path[-1] == net.start
    assert sorted(route.names[1:-1]) == ["B", "C", "D", "E"]


def test_matches_brute_force_on_random_networks():
    for n in range(1, 8):
        for seed in range(6):
            net = random_network(n, seed=seed * 31 + n)
            assert DynamicProgrammingSolver().solve(net).total_distance == pytest.approx(
                brute_force_optimum(net)
            )


def test_respects_priorities_and_matches_constrained_optimum():
    for seed in range(8):
        net = random_network(6, seed=seed, num_priority_levels=3)
        route = DynamicProgrammingSolver().solve(net)
        priorities = [loc.priority for loc in route.path[1:-1]]
        assert priorities == sorted(priorities)
        assert route.total_distance == pytest.approx(brute_force_optimum(net))


def test_too_many_stops_raises():
    net = random_network(5, seed=1)
    solver = DynamicProgrammingSolver(max_stops=4)
    assert not solver.supports(net)
    with pytest.raises(ProblemTooLargeError):
        solver.solve(net)


def test_invalid_max_stops():
    with pytest.raises(ValueError):
        DynamicProgrammingSolver(max_stops=0)
