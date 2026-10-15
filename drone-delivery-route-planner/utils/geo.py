"""Latitude/longitude <-> local kilometre conversion.

The solvers work with flat x/y coordinates in km. For a delivery area the size
of a city, a "local flat map" centred on the depot is accurate to well under 1 %:

    x (east,  km) = (longitude - depot_lon) * 111.320 * cos(depot_lat)
    y (north, km) = (latitude  - depot_lat) * 110.574
"""
from __future__ import annotations

import math
import random
from typing import List, Tuple

from utils.exceptions import InvalidInputError

KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_AT_EQUATOR = 111.320


def validate_lat_lon(lat: float, lon: float) -> None:
    if not (math.isfinite(lat) and -85.0 <= lat <= 85.0):
        raise InvalidInputError("Latitude must be between -85 and 85.")
    if not (math.isfinite(lon) and -180.0 <= lon <= 180.0):
        raise InvalidInputError("Longitude must be between -180 and 180.")


def km_to_lat_lon(x_km: float, y_km: float, depot_lat: float, depot_lon: float) -> Tuple[float, float]:
    """Convert local km offsets (east, north) from the depot into (lat, lon)."""
    lat = depot_lat + y_km / KM_PER_DEG_LAT
    lon = depot_lon + x_km / (KM_PER_DEG_LON_AT_EQUATOR * math.cos(math.radians(depot_lat)))
    return lat, lon


def lat_lon_to_km(lat: float, lon: float, depot_lat: float, depot_lon: float) -> Tuple[float, float]:
    """Inverse of :func:`km_to_lat_lon`."""
    x = (lon - depot_lon) * KM_PER_DEG_LON_AT_EQUATOR * math.cos(math.radians(depot_lat))
    y = (lat - depot_lat) * KM_PER_DEG_LAT
    return x, y


def random_points_in_disc(count: int, radius_km: float, rng: random.Random) -> List[Tuple[float, float]]:
    """``count`` points spread uniformly over a disc of ``radius_km`` around (0, 0)."""
    points = []
    for _ in range(count):
        r = radius_km * math.sqrt(rng.random())      # sqrt => uniform over the AREA
        angle = rng.uniform(0, 2 * math.pi)
        points.append((round(r * math.cos(angle), 4), round(r * math.sin(angle), 4)))
    return points
