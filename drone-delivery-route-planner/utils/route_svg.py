"""Draw the fleet plan as a self-contained SVG (works offline, no map tiles needed).

Coordinates are the local km plane, so distances on the picture are to scale.
"""
from __future__ import annotations

import math
from html import escape
from typing import List

from algorithms.fleet_planner import FleetPlan

#: One colour per drone (blue, green and orange first - like the reference design).
DRONE_COLORS = [
    "#2563eb", "#16a34a", "#f97316", "#9333ea", "#0891b2",
    "#db2777", "#854d0e", "#4b5563", "#65a30d", "#dc2626",
]
DEPOT_COLOR = "#e11d48"
UNASSIGNED_COLOR = "#6b7280"

WIDTH, PAD = 820, 46
MIN_HEIGHT, MAX_HEIGHT = 340, 620


def drone_color(drone_id: int) -> str:
    return DRONE_COLORS[(drone_id - 1) % len(DRONE_COLORS)]


def _nice_scale_km(span_km: float) -> float:
    """A round number (1, 2, 5, 10...) of about a fifth of the map width."""
    target = span_km / 5
    magnitude = 10 ** math.floor(math.log10(target)) if target > 0 else 1
    for factor in (1, 2, 5, 10):
        if factor * magnitude >= target:
            return factor * magnitude
    return 10 * magnitude


def render_plan_svg(plan: FleetPlan) -> str:
    """Return an <svg> string with colour-coded routes, numbered orders and the depot."""
    points = [(plan.depot.x, plan.depot.y)]
    for a in plan.assignments:
        points += [(s.x, s.y) for s in a.stops]
    points += [(o.x, o.y) for o in plan.unassigned]

    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span_x, span_y = max(max_x - min_x, 1e-6), max(max_y - min_y, 1e-6)
    # Make the picture as tall as the data needs (within limits) so no space is wasted.
    wanted = (WIDTH - 2 * PAD) * span_y / span_x + 2 * PAD
    HEIGHT = int(max(MIN_HEIGHT, min(MAX_HEIGHT, wanted)))
    scale = min((WIDTH - 2 * PAD) / span_x, (HEIGHT - 2 * PAD) / span_y)   # px per km
    off_x = (WIDTH - span_x * scale) / 2
    off_y = (HEIGHT - span_y * scale) / 2

    def px(x: float, y: float) -> "tuple[float, float]":
        return off_x + (x - min_x) * scale, HEIGHT - (off_y + (y - min_y) * scale)   # y points up

    out: List[str] = [
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Delivery routes map" class="route-svg">',
        '<defs>',
    ]
    for a in plan.used_assignments:
        c = drone_color(a.drone_id)
        out.append(
            f'<marker id="arrow{a.drone_id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
        )
    out.append('</defs>')
    out.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#f4f8fc" rx="8"/>')

    # light grid
    for i in range(1, 10):
        gx, gy = WIDTH * i / 10, HEIGHT * i / 10
        out.append(f'<line x1="{gx:.0f}" y1="0" x2="{gx:.0f}" y2="{HEIGHT}" stroke="#e3ebf4"/>')
        out.append(f'<line x1="0" y1="{gy:.0f}" x2="{WIDTH}" y2="{gy:.0f}" stroke="#e3ebf4"/>')

    # routes (drawn first so the markers sit on top)
    for a in plan.used_assignments:
        c = drone_color(a.drone_id)
        coords = " ".join(f"{px(l.x, l.y)[0]:.1f},{px(l.x, l.y)[1]:.1f}" for l in a.route.path)  # type: ignore[union-attr]
        out.append(f'<polyline points="{coords}" fill="none" stroke="{c}" stroke-width="2.6" '
                   f'stroke-linejoin="round" stroke-opacity="0.9"/>')
        path = a.route.path  # type: ignore[union-attr]
        for p, q in zip(path, path[1:]):          # a direction arrow in the middle of every leg
            (x1, y1), (x2, y2) = px(p.x, p.y), px(q.x, q.y)
            if math.hypot(x2 - x1, y2 - y1) < 26:
                continue
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ux, uy = (x2 - x1), (y2 - y1)
            norm = math.hypot(ux, uy)
            ux, uy = ux / norm * 5, uy / norm * 5
            out.append(f'<line x1="{mx - ux:.1f}" y1="{my - uy:.1f}" x2="{mx + ux:.1f}" y2="{my + uy:.1f}" '
                       f'stroke="{c}" stroke-width="2.6" marker-end="url(#arrow{a.drone_id})"/>')

    # numbered orders
    for a in plan.used_assignments:
        c = drone_color(a.drone_id)
        for stop in a.stops:
            x, y = px(stop.x, stop.y)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="{c}" stroke="white" stroke-width="2"/>')
            out.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-size="11" '
                       f'font-weight="700" fill="white">{escape(stop.name)}</text>')
    for order in plan.unassigned:
        x, y = px(order.x, order.y)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="white" stroke="{UNASSIGNED_COLOR}" '
                   f'stroke-width="2" stroke-dasharray="3 2"/>')
        out.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-size="11" '
                   f'font-weight="700" fill="{UNASSIGNED_COLOR}">{escape(order.name)}</text>')

    # depot
    dx, dy = px(plan.depot.x, plan.depot.y)
    out.append(f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="11" fill="{DEPOT_COLOR}" stroke="white" stroke-width="3"/>')
    out.append(f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="4" fill="white"/>')
    out.append(f'<text x="{dx:.1f}" y="{dy - 17:.1f}" text-anchor="middle" font-size="12" '
               f'font-weight="700" fill="{DEPOT_COLOR}">Depot</text>')

    # scale bar
    bar_km = _nice_scale_km(max(span_x, span_y))
    bar_px = bar_km * scale
    bx, by = 20, HEIGHT - 20
    out.append(f'<line x1="{bx}" y1="{by}" x2="{bx + bar_px:.1f}" y2="{by}" stroke="#334155" stroke-width="2"/>')
    out.append(f'<line x1="{bx}" y1="{by - 4}" x2="{bx}" y2="{by + 4}" stroke="#334155" stroke-width="2"/>')
    out.append(f'<line x1="{bx + bar_px:.1f}" y1="{by - 4}" x2="{bx + bar_px:.1f}" y2="{by + 4}" stroke="#334155" stroke-width="2"/>')
    out.append(f'<text x="{bx + bar_px / 2:.1f}" y="{by - 8}" text-anchor="middle" font-size="11" fill="#334155">'
               f'{bar_km:g} km</text>')
    out.append('<text x="{}" y="22" text-anchor="end" font-size="11" fill="#334155">N &#8593;</text>'.format(WIDTH - 14))
    out.append('</svg>')
    return "\n".join(out)
