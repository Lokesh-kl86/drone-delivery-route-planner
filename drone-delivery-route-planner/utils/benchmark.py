"""Benchmarking helpers: random problems, comparison tables, scaling tests."""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence

from algorithms.approximation import ApproximationSolver
from algorithms.branch_and_bound import BranchAndBoundSolver
from algorithms.dynamic_programming import DynamicProgrammingSolver
from algorithms.route_manager import RouteManager
from models.delivery_network import DeliveryNetwork
from models.drone import Drone
from models.location import Location
from models.route import Route


def random_network(
    num_stops: int,
    seed: Optional[int] = None,
    size: float = 100.0,
    speed: float = 30.0,
    num_priority_levels: int = 1,
) -> DeliveryNetwork:
    """Random problem on a ``size`` x ``size`` km map; the depot is at the centre."""
    rng = random.Random(seed)
    start = Location("S", size / 2, size / 2)
    stops = [
        Location(
            f"L{i + 1}",
            round(rng.uniform(0, size), 2),
            round(rng.uniform(0, size), 2),
            rng.randint(1, num_priority_levels),
        )
        for i in range(num_stops)
    ]
    return DeliveryNetwork(start, stops, Drone(speed_kmh=speed))


def format_comparison_table(routes: Sequence[Route]) -> str:
    """Table: Algorithm | Distance | Execution Time | gap to the best distance."""
    best = min(r.total_distance for r in routes)
    rows = []
    for r in routes:
        gap = (r.total_distance / best - 1) * 100 if best > 0 else 0.0
        rows.append((r.algorithm, f"{r.total_distance:.2f} km",
                     f"{r.execution_time:.4f} s", f"+{gap:.2f}%"))
    headers = ("Algorithm", "Distance", "Execution Time", "vs Best")
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]

    def line(cells: Sequence[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    return "\n".join([line(headers), "-+-".join("-" * w for w in widths), *(line(r) for r in rows)])


def scaling_benchmark(sizes: Sequence[int], seed: int = 42) -> List[Dict[str, Any]]:
    """Run every applicable algorithm one after another on random problems of growing size."""
    solvers = {
        "dp": DynamicProgrammingSolver(),
        "bnb": BranchAndBoundSolver(),
        "approx": ApproximationSolver(),
    }
    rows: List[Dict[str, Any]] = []
    for n in sizes:
        network = random_network(n, seed=seed + n)
        row: Dict[str, Any] = {"stops": n}
        for key, solver in solvers.items():
            if solver.supports(network):
                route = solver.solve(network)
                row[key] = (route.total_distance, route.execution_time)
            else:
                row[key] = None
        rows.append(row)
    return rows


def format_scaling_table(rows: Sequence[Dict[str, Any]]) -> str:
    """Pretty-print scaling_benchmark results (times in seconds)."""
    def t(cell: Optional[Any]) -> str:
        return "skipped" if cell is None else f"{cell[1]:.4f}"

    headers = ("Stops", "DP (s)", "B&B (s)", "Approx (s)", "Approx gap")
    body = []
    for row in rows:
        exact = [row[k][0] for k in ("dp", "bnb") if row[k] is not None]
        gap = f"+{(row['approx'][0] / min(exact) - 1) * 100:.2f}%" if exact else "n/a"
        body.append((str(row["stops"]), t(row["dp"]), t(row["bnb"]), t(row["approx"]), gap))
    widths = [max(len(h), *(len(r[i]) for r in body)) for i, h in enumerate(headers)]

    def line(cells: Sequence[str]) -> str:
        return " | ".join(c.rjust(widths[i]) for i, c in enumerate(cells))

    return "\n".join([line(headers), "-+-".join("-" * w for w in widths), *(line(r) for r in body)])


def parallel_speedup_benchmark(
    num_stops: int = 200,
    restarts: int = 200,
    processes: Optional[int] = None,
    seed: int = 7,
) -> Dict[str, Any]:
    """Time the same multi-start search run in one process vs. spread over several."""
    network = random_network(num_stops, seed=seed)
    manager = RouteManager(network, processes=processes)
    sequential = manager.solve_large_parallel(restarts, seed=seed, parallel=False)
    parallel = manager.solve_large_parallel(restarts, seed=seed, parallel=True)
    return {
        "stops": num_stops,
        "restarts": restarts,
        "processes": manager.processes,
        "sequential_time": sequential.execution_time,
        "parallel_time": parallel.execution_time,
        "speedup": sequential.execution_time / parallel.execution_time if parallel.execution_time else 0.0,
        "distance": parallel.total_distance,
        "same_result": abs(sequential.total_distance - parallel.total_distance) < 1e-9,
    }
