"""Reading and validating user input (keyboard, JSON file) and the demo data."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from models.delivery_network import DeliveryNetwork
from models.drone import DEFAULT_SPEED_KMH, Drone
from models.location import Location
from utils.exceptions import InvalidInputError

MAX_DELIVERIES = 200


# --------------------------------------------------------------------- parsing
def parse_location_line(text: str, default_priority: int = 1) -> Location:
    """Turn text such as ``B 2 3``, ``B(2,3)`` or ``B 2 3 1`` into a Location.

    Format: name x y [priority]. Brackets and commas are allowed as separators.
    Raises InvalidInputError with a helpful message when the text is wrong.
    """
    tokens = re.sub(r"[(),;]", " ", text).split()
    if len(tokens) not in (3, 4):
        raise InvalidInputError(
            f"Could not read '{text.strip()}'. Use: name x y [priority]  (e.g. B 2 3 or B(2,3))."
        )
    name = tokens[0]
    try:
        x, y = float(tokens[1]), float(tokens[2])
    except ValueError:
        raise InvalidInputError(f"Coordinates in '{text.strip()}' must be numbers.") from None
    priority = default_priority
    if len(tokens) == 4:
        try:
            priority = int(tokens[3])
        except ValueError:
            raise InvalidInputError(
                f"Priority in '{text.strip()}' must be a whole number (1 = most urgent)."
            ) from None
    return Location(name, x, y, priority)    # Location validates the values


def parse_positive_int(text: str, label: str, maximum: Optional[int] = None) -> int:
    try:
        value = int(text.strip())
    except ValueError:
        raise InvalidInputError(f"{label} must be a whole number.") from None
    if value < 1:
        raise InvalidInputError(f"{label} must be at least 1.")
    if maximum is not None and value > maximum:
        raise InvalidInputError(f"{label} must be at most {maximum}.")
    return value


def parse_speed(text: str) -> float:
    try:
        speed = float(text.strip())
    except ValueError:
        raise InvalidInputError("Drone speed must be a number (km/h).") from None
    Drone(speed_kmh=speed)                   # raises InvalidInputError if not positive/finite
    return speed


# ------------------------------------------------------------- interactive CLI
def _ask(prompt: str, parser: Callable[[str], Any], input_fn: Callable[[str], str],
         output_fn: Callable[[str], None], default: Optional[str] = None) -> Any:
    """Keep asking until ``parser`` accepts the answer."""
    while True:
        answer = input_fn(prompt).strip()
        if not answer and default is not None:
            answer = default
        try:
            return parser(answer)
        except InvalidInputError as exc:
            output_fn(f"  ! {exc}")


def read_network_interactively(
    speed: Optional[float] = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> DeliveryNetwork:
    """Ask the user for the whole problem, re-asking on every invalid answer."""
    output_fn("Enter locations as:  name x y [priority]   (coordinates in km, priority 1 = most urgent)")
    output_fn("Examples:  B 2 3     B(2,3)     C 5 2 2")
    output_fn("")

    count = _ask("Number of delivery locations (not counting the start): ",
                 lambda t: parse_positive_int(t, "Number of locations", MAX_DELIVERIES),
                 input_fn, output_fn)
    start = _ask("Start location [default: A 0 0]: ", parse_location_line,
                 input_fn, output_fn, default="A 0 0")
    start = Location(start.name, start.x, start.y)   # the depot has no priority

    deliveries: List[Location] = []
    used_names = {start.name.lower()}
    while len(deliveries) < count:
        location = _ask(f"Delivery location {len(deliveries) + 1}/{count}: ",
                        parse_location_line, input_fn, output_fn)
        if location.name.lower() in used_names:
            output_fn(f"  ! The name '{location.name}' is already used. Pick a different name.")
            continue
        used_names.add(location.name.lower())
        deliveries.append(location)

    if speed is None:
        speed = _ask(f"Drone speed in km/h [default: {DEFAULT_SPEED_KMH:g}]: ", parse_speed,
                     input_fn, output_fn, default=str(DEFAULT_SPEED_KMH))
    return DeliveryNetwork(start, deliveries, Drone(speed_kmh=speed))


# ------------------------------------------------------------------- JSON file
def load_network_from_json(path: str, speed_override: Optional[float] = None) -> DeliveryNetwork:
    """Load a problem from a JSON file (see data/sample_input.json)."""
    try:
        data: Dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InvalidInputError(f"File not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise InvalidInputError(f"'{path}' is not valid JSON: {exc}") from None

    try:
        start_data = data["start"]
        start = Location(start_data["name"], start_data["x"], start_data["y"])
        deliveries = [
            Location(d["name"], d["x"], d["y"], d.get("priority", 1))
            for d in data["deliveries"]
        ]
    except (KeyError, TypeError) as exc:
        raise InvalidInputError(
            f"'{path}' is missing required data ({exc}). Expected 'start' and 'deliveries'."
        ) from None

    drone_data = data.get("drone", {})
    speed = speed_override if speed_override is not None else drone_data.get("speed_kmh", DEFAULT_SPEED_KMH)
    return DeliveryNetwork(start, deliveries, Drone(drone_data.get("name", "Drone-1"), speed))


# ------------------------------------------------------------------- demo data
def demo_network(speed: Optional[float] = None) -> DeliveryNetwork:
    """The example from the project brief: A(0,0) is the start."""
    start = Location("A", 0, 0)
    deliveries = [Location("B", 2, 3), Location("C", 5, 2), Location("D", 6, 6), Location("E", 1, 5)]
    return DeliveryNetwork(start, deliveries, Drone(speed_kmh=speed or DEFAULT_SPEED_KMH))
