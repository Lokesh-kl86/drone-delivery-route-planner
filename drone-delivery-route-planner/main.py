"""Drone Delivery Route Planner - command line entry point.

Examples
--------
    python main.py                         # type the locations in
    python main.py --demo                  # the 5-location example from the brief
    python main.py --file data/sample_input.json
    python main.py --random 12 --seed 1    # random problem with 12 stops
    python main.py --benchmark             # algorithm scaling + parallel speed-up
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from algorithms.dynamic_programming import DEFAULT_MAX_STOPS as DP_LIMIT
from algorithms.route_manager import RouteManager
from models.delivery_network import DeliveryNetwork
from utils.benchmark import (
    format_comparison_table,
    format_scaling_table,
    parallel_speedup_benchmark,
    random_network,
    scaling_benchmark,
)
from utils.exceptions import DroneRouteError
from utils.input_handler import demo_network, load_network_from_json, read_network_interactively
from utils.report import format_route_report


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drone Delivery Route Planner (TSP).")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--demo", action="store_true", help="use the built-in 5-location example")
    source.add_argument("--file", metavar="JSON", help="load locations from a JSON file")
    source.add_argument("--random", type=int, metavar="N", help="generate N random delivery stops")
    parser.add_argument("--seed", type=int, default=None, help="random seed (for --random and restarts)")
    parser.add_argument("--speed", type=float, default=None, help="drone speed in km/h (default 30)")
    parser.add_argument("--restarts", type=int, default=None,
                        help="parallel multi-start restarts for the approximation "
                             f"(default: 32 when stops > {DP_LIMIT}, otherwise off)")
    parser.add_argument("--processes", type=int, default=None, help="worker processes (default: all CPUs)")
    parser.add_argument("--sequential", action="store_true", help="do not use multiprocessing")
    parser.add_argument("--no-plot", action="store_true", help="do not open the matplotlib window")
    parser.add_argument("--save", metavar="PNG", help="save the route plot to this image file")
    parser.add_argument("--benchmark", action="store_true", help="run the benchmark suite and exit")
    return parser.parse_args(argv)


def build_network(args: argparse.Namespace) -> DeliveryNetwork:
    """Create the problem from whichever input source the user chose."""
    if args.file:
        return load_network_from_json(args.file, args.speed)
    if args.random is not None:
        if args.random < 1:
            raise DroneRouteError("--random needs at least 1 stop.")
        return random_network(args.random, seed=args.seed, speed=args.speed or 30.0)
    if args.demo:
        return demo_network(args.speed)
    return read_network_interactively(speed=args.speed)


def run_benchmark(processes: Optional[int]) -> None:
    print("\n=== Scaling benchmark (random maps, algorithms run one after another) ===")
    print(format_scaling_table(scaling_benchmark([4, 6, 8, 10, 12, 14, 16, 20, 30])))
    print("\n('skipped' = the exact algorithm is limited to small inputs)")

    print("\n=== Multiprocessing speed-up (multi-start 2-opt) ===")
    result = parallel_speedup_benchmark(processes=processes)
    print(f"{result['stops']} stops, {result['restarts']} restarts, {result['processes']} CPU process(es)")
    print(f"  one process : {result['sequential_time']:.3f} s")
    print(f"  in parallel : {result['parallel_time']:.3f} s   (speed-up x{result['speedup']:.2f})")
    print(f"  same best tour found: {result['same_result']}  ({result['distance']:.2f} km)")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.benchmark:
        run_benchmark(args.processes)
        return 0

    try:
        network = build_network(args)
        manager = RouteManager(network, processes=args.processes)

        restarts = args.restarts
        if restarts is None:
            restarts = 32 if network.num_stops > DP_LIMIT else 0
        result = manager.compare(
            parallel=not args.sequential, multistart_restarts=restarts, seed=args.seed
        )
    except DroneRouteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nInput cancelled.", file=sys.stderr)
        return 1

    best = result.best_route
    print()
    print(format_route_report(best, network))

    print("\nAlgorithm Comparison")
    print(format_comparison_table(result.routes))
    for name, reason in result.skipped.items():
        print(f"  (skipped {name}: {reason})")
    for route in result.routes:
        if "nodes_explored" in route.stats:
            print(f"  Branch and Bound explored {route.stats['nodes_explored']:,} nodes "
                  f"and pruned {route.stats['nodes_pruned']:,} branches.")

    mode = "in parallel" if result.parallel else "sequentially"
    print(f"\nRan {len(result.routes) - (1 if restarts else 0)} algorithm(s) {mode}: "
          f"wall-clock {result.wall_time:.3f} s, sum of individual times {result.sequential_time:.3f} s")
    for note in result.notes:
        print(f"  Note: {note}")

    if not args.no_plot or args.save:
        # Imported here so worker processes do not pay the cost of loading matplotlib.
        from utils.visualization import plot_route

        plot_route(best, save_path=args.save, show=not args.no_plot)
        if args.save:
            print(f"Route plot saved to {args.save}")
    return 0


if __name__ == "__main__":      # required for multiprocessing on Windows/macOS
    sys.exit(main())
