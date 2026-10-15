"""DeliveryNetwork validation, priorities and Route generation."""
import pytest

from models import DeliveryNetwork, Location, Route
from tests.helpers import example_network
from utils.exceptions import InvalidInputError


def test_network_counts():
    net = example_network()
    assert net.num_locations == 5 and net.num_stops == 4
    assert net.start.name == "A"


def test_network_needs_at_least_one_delivery():
    with pytest.raises(InvalidInputError):
        DeliveryNetwork(Location("A", 0, 0), [])


def test_network_rejects_duplicate_names_case_insensitive():
    with pytest.raises(InvalidInputError):
        DeliveryNetwork(Location("A", 0, 0), [Location("b", 1, 1), Location("B", 2, 2)])
    with pytest.raises(InvalidInputError):
        DeliveryNetwork(Location("A", 0, 0), [Location("A", 1, 1)])


def test_required_masks_follow_priorities():
    net = DeliveryNetwork(
        Location("S", 0, 0),
        [Location("X", 1, 0, 1), Location("Y", 2, 0, 2), Location("Z", 3, 0, 2)],
    )
    # stop numbers: X=0, Y=1, Z=2  ->  Y and Z must wait for X
    assert net.required_masks() == [0, 0b001, 0b001]
    assert net.has_priorities
    assert net.is_priority_valid([1, 3, 2])
    assert not net.is_priority_valid([2, 1, 3])


def test_no_priorities_means_no_rules():
    net = example_network()
    assert not net.has_priorities
    assert net.required_masks() == [0, 0, 0, 0]


def test_route_from_indices_builds_correct_totals():
    net = example_network(speed=30)
    route = Route.from_indices(net, [0, 1, 2, 3, 4, 0], "Manual")
    expected = net.path_distance([0, 1, 2, 3, 4, 0])
    assert route.total_distance == pytest.approx(expected)
    assert route.estimated_time_minutes == pytest.approx(expected * 2)   # 30 km/h
    assert route.path_string() == "A -> B -> C -> D -> E -> A"
    assert route.num_locations_visited == 5
    assert route.num_deliveries == 4


def test_route_rejects_invalid_tours():
    net = example_network()
    with pytest.raises(ValueError):
        Route.from_indices(net, [0, 1, 2, 3, 0], "missing a stop")
    with pytest.raises(ValueError):
        Route.from_indices(net, [0, 1, 1, 3, 4, 0], "repeated stop")
    with pytest.raises(ValueError):
        Route.from_indices(net, [1, 2, 3, 4, 0], "does not start at depot")
    with pytest.raises(ValueError):
        Route.from_indices(net, [0, 1, 2, 3, 4, 1], "does not return to depot")
