"""RouteManager: runs the solvers (in parallel if possible) and compares them.

Two kinds of parallel work are supported with ``multiprocessing.Pool``:

1. ``compare``: run DP, Branch and Bound and the approximation at the same
   time, each in its own process, and compare results and execution times.
2. ``solve_large_parallel``: for big problems, split many random-restart
   2-opt searches across all CPU cores and keep the best tour.

Note for Windows/macOS: multiprocessing starts fresh Python processes, so the
program's entry point must be protected by ``if __name__ == "__main__":``
(main.py already does this).
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from algorithms.approximation import ApproximationSolver
from algorithms.base import TSPOptimizer
from algorithms.branch_and_bound import BranchAndBoundSolver
from algorithms.dynamic_programming import DynamicProgrammingSolver
from models.delivery_network import DeliveryNetwork
from models.route import Route
from utils.exceptions import InvalidInputError


def _run_solver(solver: TSPOptimizer, network: DeliveryNetwork) -> Route:
    """Worker function. It lives at module level so multiprocessing can pickle it."""
    return solver.solve(network)


@dataclass
class ComparisonResult:
    """Everything produced by RouteManager.compare."""

    routes: List[Route]
    skipped: Dict[str, str] = field(default_factory=dict)   # solver name -> reason
    wall_time: float = 0.0          # real time the solver phase took
    sequential_time: float = 0.0    # sum of the individual run times
    parallel: bool = False          # did the solvers really run in separate processes?
    notes: List[str] = field(default_factory=list)

    @property
    def best_route(self) -> Route:
        """Shortest tour; if two are equally short the faster algorithm wins."""
        return min(self.routes, key=lambda r: (round(r.total_distance, 9), r.execution_time))


class RouteManager:
    """Coordinates the solvers for one DeliveryNetwork."""

    def __init__(self, network: DeliveryNetwork, processes: Optional[int] = None) -> None:
        if processes is not None and processes < 1:
            raise InvalidInputError("Number of processes must be at least 1.")
        self.network = network
        self.processes = processes or os.cpu_count() or 1

    # ----------------------------------------------------------------- solvers
    @staticmethod
    def default_solvers() -> List[TSPOptimizer]:
        return [DynamicProgrammingSolver(), BranchAndBoundSolver(), ApproximationSolver()]

    def solve(self, solver: TSPOptimizer) -> Route:
        """Run a single solver in this process."""
        return solver.solve(self.network)

    def solve_auto(self) -> Route:
        """Pick the best sensible algorithm: exact DP when small, heuristic otherwise."""
        dp = DynamicProgrammingSolver()
        solver: TSPOptimizer = dp if dp.supports(self.network) else ApproximationSolver()
        return self.solve(solver)

    # --------------------------------------------------------- parallel helper
    def _run_many(
        self, solvers: Sequence[TSPOptimizer], parallel: bool
    ) -> Tuple[List[Route], bool, Optional[str]]:
        """Run solvers in a process pool. Falls back to a plain loop if that fails."""
        note: Optional[str] = None
        if parallel and len(solvers) > 1:
            try:
                workers = min(self.processes, len(solvers))
                with mp.Pool(processes=workers) as pool:
                    pending = [pool.apply_async(_run_solver, (s, self.network)) for s in solvers]
                    return [p.get() for p in pending], True, None
            except (OSError, ImportError) as exc:   # e.g. sandboxed environments
                note = f"Multiprocessing unavailable ({exc}); ran sequentially instead."
        return [_run_solver(s, self.network) for s in solvers], False, note

    # ------------------------------------------------------------- comparisons
    def compare(
        self,
        solvers: Optional[Sequence[TSPOptimizer]] = None,
        parallel: bool = True,
        multistart_restarts: int = 0,
        seed: Optional[int] = None,
    ) -> ComparisonResult:
        """Run several algorithms (in parallel) and collect their routes.

        Solvers that cannot handle the problem size are skipped, not failed.
        If ``multistart_restarts`` > 0 a parallel multi-start approximation is
        run afterwards and added to the results.
        """
        candidates = list(solvers) if solvers is not None else self.default_solvers()
        runnable: List[TSPOptimizer] = []
        skipped: Dict[str, str] = {}
        for solver in candidates:
            if solver.supports(self.network):
                runnable.append(solver)
            else:
                skipped[solver.name] = (
                    f"limited to {solver.max_stops} stops (network has {self.network.num_stops})"
                )
        if not runnable:
            raise InvalidInputError("None of the requested algorithms can solve this network.")

        started = time.perf_counter()
        routes, used_parallel, note = self._run_many(runnable, parallel)
        wall = time.perf_counter() - started
        sequential = sum(r.execution_time for r in routes)

        notes = [note] if note else []
        if multistart_restarts > 0:
            routes.append(self.solve_large_parallel(multistart_restarts, seed, parallel))

        return ComparisonResult(routes, skipped, wall, sequential, used_parallel, notes)

    def solve_large_parallel(
        self,
        total_restarts: int = 32,
        seed: Optional[int] = None,
        parallel: bool = True,
    ) -> Route:
        """Multi-start 2-opt with the restarts shared between CPU cores.

        Each worker runs its own batch of random restarts; the shortest tour
        from all workers is returned. The reported execution time is the real
        (wall-clock) time of the whole operation.
        """
        if total_restarts < 1:
            raise InvalidInputError("Number of restarts must be at least 1.")
        workers = min(self.processes, total_restarts)
        base, extra = divmod(total_restarts, workers)
        base_seed = seed if seed is not None else int(time.time())
        solvers = [
            ApproximationSolver(
                restarts=base + (1 if k < extra else 0),
                seed=base_seed + k,
                use_greedy_start=(k == 0),   # one worker also tries the greedy tour
            )
            for k in range(workers)
        ]

        started = time.perf_counter()
        routes, used_parallel, _ = self._run_many(solvers, parallel)
        elapsed = time.perf_counter() - started

        best = min(routes, key=lambda r: r.total_distance)
        label = f"Approximation (parallel multi-start, {total_restarts} restarts)"
        return replace(
            best,
            algorithm=label,
            execution_time=elapsed,
            stats={"restarts": total_restarts, "workers": workers, "parallel": used_parallel},
        )
