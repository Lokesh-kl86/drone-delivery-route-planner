"""Parsing and validating user input."""
import json

import pytest

from utils.exceptions import InvalidInputError
from utils.input_handler import (
    demo_network,
    load_network_from_json,
    parse_location_line,
    parse_positive_int,
    parse_speed,
    read_network_interactively,
)


def test_parse_location_formats():
    for text in ("B 2 3", "B(2,3)", "B (2, 3)", "B,2,3"):
        loc = parse_location_line(text)
        assert (loc.name, loc.x, loc.y, loc.priority) == ("B", 2.0, 3.0, 1)
    assert parse_location_line("C 5 2 3").priority == 3
    assert parse_location_line("D -1.5 2.25").x == -1.5


def test_parse_location_errors():
    for bad in ("", "B", "B 2", "B two 3", "B 2 3 high", "B 2 3 0", "B 2 3 1 9", "B nan 3"):
        with pytest.raises(InvalidInputError):
            parse_location_line(bad)


def test_parse_numbers():
    assert parse_positive_int(" 5 ", "N") == 5
    for bad in ("0", "-2", "abc", "2.5"):
        with pytest.raises(InvalidInputError):
            parse_positive_int(bad, "N")
    with pytest.raises(InvalidInputError):
        parse_positive_int("500", "N", maximum=200)
    assert parse_speed("45.5") == 45.5
    for bad in ("0", "-3", "fast", "inf"):
        with pytest.raises(InvalidInputError):
            parse_speed(bad)


def test_interactive_input_reprompts_on_bad_answers():
    answers = iter([
        "abc",            # bad count
        "2",              # count
        "S 0 0",          # start
        "P 3 4",          # stop 1
        "P 1 1",          # duplicate name -> rejected
        "Q 6 8 2",        # stop 2 with priority 2
        "zero",           # bad speed
        "50",             # speed
    ])
    messages = []
    net = read_network_interactively(input_fn=lambda _p: next(answers), output_fn=messages.append)
    assert [d.name for d in net.deliveries] == ["P", "Q"]
    assert net.deliveries[1].priority == 2
    assert net.drone.speed_kmh == 50
    assert any("already used" in m for m in messages)
    assert any("whole number" in m for m in messages)


def test_interactive_defaults_for_start_and_speed():
    answers = iter(["1", "", "B 2 3", ""])
    net = read_network_interactively(input_fn=lambda _p: next(answers), output_fn=lambda _m: None)
    assert (net.start.name, net.start.x, net.start.y) == ("A", 0, 0)
    assert net.drone.speed_kmh == 30


def test_load_json(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps({
        "drone": {"speed_kmh": 60},
        "start": {"name": "A", "x": 0, "y": 0},
        "deliveries": [{"name": "B", "x": 1, "y": 1, "priority": 2}, {"name": "C", "x": 2, "y": 2}],
    }))
    net = load_network_from_json(str(path))
    assert net.num_stops == 2 and net.drone.speed_kmh == 60
    assert net.deliveries[0].priority == 2 and net.deliveries[1].priority == 1
    assert load_network_from_json(str(path), speed_override=10).drone.speed_kmh == 10


def test_load_json_errors(tmp_path):
    with pytest.raises(InvalidInputError):
        load_network_from_json(str(tmp_path / "missing.json"))
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(InvalidInputError):
        load_network_from_json(str(broken))
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"start": {"name": "A", "x": 0, "y": 0}}))
    with pytest.raises(InvalidInputError):
        load_network_from_json(str(incomplete))


def test_demo_network_matches_the_brief():
    net = demo_network()
    assert [loc.name for loc in net.locations] == ["A", "B", "C", "D", "E"]
