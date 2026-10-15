"""Flask website, form validation, order generation and the SVG map."""
import math
import random
import xml.dom.minidom

import pytest

from algorithms.fleet_planner import FleetPlanner
from app import create_app
from models import Location
from utils.geo import km_to_lat_lon, lat_lon_to_km, random_points_in_disc
from utils.route_svg import render_plan_svg
from utils.web_service import (
    DEFAULT_FORM,
    MAX_DRONES,
    MAX_ORDERS,
    build_plan_view,
    generate_orders,
    parse_plan_form,
)

VALID = {"orders": "10", "drones": "3", "depot": "17.3850, 78.4867", "seed": "4"}


def client():
    return create_app().test_client()


# ---------------------------------------------------------------- pages
def test_home_page_shows_the_form():
    r = client().get("/")
    html = r.data.decode()
    assert r.status_code == 200
    for needle in ("Number of Orders", "Number of Drones", "Plan Routes", "17.3850, 78.4867"):
        assert needle in html


def test_plan_shows_results():
    r = client().post("/plan", data=VALID)
    html = r.data.decode()
    assert r.status_code == 200
    for needle in ("Total Orders", "Drones Used", "Total Distance", "Drone Assignments",
                   "Route Distance Summary", "<svg", "Drone 1", "Drone 3"):
        assert needle in html


def test_same_seed_gives_the_same_page_content():
    a = client().post("/plan", data=VALID).data.decode()
    b = client().post("/plan", data=VALID).data.decode()
    assert a == b


def test_results_come_from_the_real_planner():
    request, errors = parse_plan_form(VALID)
    assert errors == []
    view = build_plan_view(request)
    depot = Location("Depot", 0, 0)
    direct = FleetPlanner(3, 30.0, None, seed=4).plan(depot, generate_orders(10, 8.0, 4))
    assert view["total_distance"] == pytest.approx(direct.total_distance_km)
    assert f"{direct.total_distance_km:.1f} km" in client().post("/plan", data=VALID).data.decode()


def test_bad_input_returns_friendly_errors_and_keeps_values():
    r = client().post("/plan", data={"orders": "0", "drones": "abc", "depot": "hello"})
    html = r.data.decode()
    assert r.status_code == 400
    assert "Number of orders must be between 1 and" in html
    assert "Number of drones must be a whole number" in html
    assert "Depot location must look like" in html
    assert 'value="hello"' in html                        # what the user typed is kept


def test_battery_scenario_shows_warnings_and_unassigned():
    data = dict(VALID, battery="8")
    html = client().post("/plan", data=data).data.decode()
    assert "Warnings" in html and "Unassigned orders" in html
    assert "is unassigned" in html and "Battery Used" in html


def test_get_plan_redirects_home():
    r = client().get("/plan")
    assert r.status_code == 302 and r.headers["Location"].endswith("/")


def test_unknown_page_is_404():
    assert client().get("/nope").status_code == 404


# ----------------------------------------------------------- validation
def test_parse_valid_form():
    request, errors = parse_plan_form(DEFAULT_FORM)
    assert errors == []
    assert (request.num_orders, request.num_drones) == (10, 3)
    assert request.depot_lat == pytest.approx(17.385) and request.depot_lon == pytest.approx(78.4867)
    assert request.max_range_km is None and request.seed is None


def test_parse_rejects_bad_values():
    cases = [
        ({"orders": "-1"}, "Number of orders"),
        ({"orders": str(MAX_ORDERS + 1)}, "Number of orders"),
        ({"orders": "2.5"}, "Number of orders"),
        ({"drones": "0"}, "Number of drones"),
        ({"drones": str(MAX_DRONES + 1)}, "Number of drones"),
        ({"depot": "95, 10"}, "Latitude"),
        ({"depot": "10, 200"}, "Longitude"),
        ({"depot": "10"}, "Depot location"),
        ({"depot": "a, b"}, "numbers"),
        ({"battery": "-5"}, "Battery range"),
        ({"battery": "abc"}, "Battery range"),
        ({"speed": "0"}, "Drone speed"),
        ({"speed": "nan"}, "Drone speed"),
        ({"radius": "1000"}, "Delivery radius"),
        ({"seed": "x"}, "seed"),
    ]
    for change, expected in cases:
        request, errors = parse_plan_form({**DEFAULT_FORM, **change})
        assert request is None, change
        assert any(expected in e for e in errors), (change, errors)


def test_parse_optional_fields():
    request, errors = parse_plan_form({**DEFAULT_FORM, "battery": "25.5", "seed": "7", "speed": "40"})
    assert errors == []
    assert (request.max_range_km, request.seed, request.speed_kmh) == (25.5, 7, 40.0)


# ------------------------------------------------------ orders and geometry
def test_generate_orders_is_reproducible_and_inside_the_radius():
    a, b = generate_orders(25, 6.0, seed=3), generate_orders(25, 6.0, seed=3)
    assert [(o.name, o.x, o.y) for o in a] == [(o.name, o.x, o.y) for o in b]
    assert [o.name for o in a] == [str(i) for i in range(1, 26)]
    assert all(math.hypot(o.x, o.y) <= 6.0 + 1e-6 for o in a)
    assert generate_orders(25, 6.0, seed=4)[0] != a[0]


def test_lat_lon_conversion_round_trip_and_scale():
    lat, lon = km_to_lat_lon(3.0, 4.0, 17.385, 78.4867)
    x, y = lat_lon_to_km(lat, lon, 17.385, 78.4867)
    assert (x, y) == (pytest.approx(3.0), pytest.approx(4.0))
    assert lat - 17.385 == pytest.approx(4.0 / 110.574)           # ~0.036 degrees for 4 km north


def test_random_points_use_the_whole_disc():
    pts = random_points_in_disc(500, 10.0, random.Random(1))
    radii = sorted(math.hypot(x, y) for x, y in pts)
    assert 4.0 < radii[len(radii) // 2] < 8.5       # median radius of a uniform disc is ~7.07


# ------------------------------------------------------------------ SVG map
def test_svg_is_valid_xml_and_labels_every_order():
    orders = generate_orders(12, 8.0, seed=2)
    plan = FleetPlanner(3).plan(Location("Depot", 0, 0), orders)
    svg = render_plan_svg(plan)
    xml.dom.minidom.parseString(svg)                  # raises if the XML is broken
    for o in orders:
        assert f">{o.name}</text>" in svg
    assert svg.count("<polyline") == plan.drones_used


def test_svg_handles_unassigned_orders_and_a_single_order():
    orders = generate_orders(6, 8.0, seed=2)
    plan = FleetPlanner(2, max_range_km=9).plan(Location("Depot", 0, 0), orders)
    xml.dom.minidom.parseString(render_plan_svg(plan))
    one = FleetPlanner(1).plan(Location("Depot", 0, 0), [Location("1", 3, 4)])
    xml.dom.minidom.parseString(render_plan_svg(one))
