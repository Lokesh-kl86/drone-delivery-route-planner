"""2D plot of the drone route (matplotlib)."""
from __future__ import annotations

from typing import Optional, Sequence

import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from models.route import Route

START_COLOR = "#d62728"
STOP_COLOR = "#1f77b4"
ARROW_COLOR = "#2ca02c"


def _draw_route(ax: Axes, route: Route) -> None:
    """Draw one route on an existing axes."""
    path = route.path
    start = path[0]
    stops = path[1:-1]

    # Legs with arrows showing the flying direction.
    for a, b in zip(path, path[1:]):
        ax.annotate(
            "", xy=(b.x, b.y), xytext=(a.x, a.y),
            arrowprops=dict(arrowstyle="-|>", color=ARROW_COLOR, lw=1.8,
                            shrinkA=9, shrinkB=9, mutation_scale=16),
        )

    # Delivery stops, numbered in visiting order.
    ax.scatter([s.x for s in stops], [s.y for s in stops], s=170, color=STOP_COLOR,
               zorder=3, label="Delivery stop")
    show_priority = len({s.priority for s in stops}) > 1
    for order, stop in enumerate(stops, start=1):
        label = f"{stop.name}" + (f" (P{stop.priority})" if show_priority else "")
        ax.annotate(str(order), (stop.x, stop.y), color="white", ha="center", va="center",
                    fontsize=8, fontweight="bold", zorder=4)
        ax.annotate(label, (stop.x, stop.y), xytext=(0, 13), textcoords="offset points",
                    ha="center", fontsize=10)

    # Start / end point.
    ax.scatter([start.x], [start.y], s=300, marker="*", color=START_COLOR, zorder=3,
               label="Start / end")
    ax.annotate(f"{start.name} (start)", (start.x, start.y), xytext=(0, -20),
                textcoords="offset points", ha="center", fontsize=10, fontweight="bold")

    ax.set_title(f"{route.algorithm}\n{route.total_distance:.2f} km, "
                 f"{route.estimated_time_minutes:.1f} min", fontsize=10)
    ax.set_xlabel("x (km)")
    ax.set_ylabel("y (km)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.margins(0.12)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="best", fontsize=8)


def plot_route(route: Route, save_path: Optional[str] = None, show: bool = True) -> None:
    """Plot locations, start point, route and direction arrows."""
    fig, ax = plt.subplots(figsize=(7, 6))
    _draw_route(ax, route)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def plot_comparison(routes: Sequence[Route], save_path: Optional[str] = None,
                    show: bool = True) -> None:
    """Draw several routes side by side (one panel per algorithm)."""
    fig, axes = plt.subplots(1, len(routes), figsize=(6 * len(routes), 5.5), squeeze=False)
    for ax, route in zip(axes[0], routes):
        _draw_route(ax, route)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
