"""Distance calculation, Location and Drone basics."""
import math

import pytest

from models import Drone, Location
from utils.distance import build_distance_matrix, euclidean_distance, path_length
from utils.exceptions import InvalidInputError


def test_euclidean_distance_3_4_5_triangle():
    assert euclidean_distance(Location("A", 0, 0), Location("B", 3, 4)) == pytest.approx(5.0)


def test_distance_to_self_is_zero():
    a = Location("A", 2.5, -1.5)
    assert a.distance_to(a) == 0.0


def test_distance_is_symmetric():
    a, b = Location("A", 1, 2), Location("B", -4, 7)
    assert a.distance_to(b) == pytest.approx(b.distance_to(a))


def test_distance_with_negative_and_decimal_coordinates():
    a, b = Location("A", -1.5, -2.0), Location("B", 1.5, 2.0)
    assert a.distance_to(b) == pytest.approx(5.0)


def test_distance_matrix_shape_symmetry_and_diagonal():
    points = [Location("A", 0, 0), Location("B", 2, 3), Location("C", 5, 2)]
    matrix = build_distance_matrix(points)
    assert len(matrix) == 3 and all(len(row) == 3 for row in matrix)
    for i in range(3):
        assert matrix[i][i] == 0.0
        for j in range(3):
            assert matrix[i][j] == pytest.approx(matrix[j][i])
    assert matrix[0][1] == pytest.approx(math.sqrt(13))


def test_path_length_adds_up_the_legs():
    matrix = build_distance_matrix([Location("A", 0, 0), Location("B", 3, 4), Location("C", 3, 0)])
    assert path_length([0, 1, 2, 0], matrix) == pytest.approx(5 + 4 + 3)


def test_drone_time_matches_example_from_brief():
    # 18.42 km at 30 km/h = 36.84 minutes
    assert Drone(speed_kmh=30).travel_time_minutes(18.42) == pytest.approx(36.84)


def test_drone_rejects_bad_speed():
    for bad in (0, -5, float("nan"), float("inf"), "fast"):
        with pytest.raises(InvalidInputError):
            Drone(speed_kmh=bad)


def test_location_rejects_bad_values():
    with pytest.raises(InvalidInputError):
        Location("", 0, 0)
    with pytest.raises(InvalidInputError):
        Location("A", "x", 0)
    with pytest.raises(InvalidInputError):
        Location("A", float("nan"), 0)
    with pytest.raises(InvalidInputError):
        Location("A", 0, 0, priority=0)
    with pytest.raises(InvalidInputError):
        Location("A", 0, 0, priority=1.5)
