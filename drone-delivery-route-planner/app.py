"""Drone Delivery Route Planner - Flask web interface.

Run:   python app.py        then open  http://127.0.0.1:5000
(or simply:  python start.py  - it sets everything up and opens the browser)

The page only collects inputs and shows results. All route planning is done by
the project's real algorithms (algorithms/ and models/); the command line
program (python main.py) keeps working exactly as before.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from flask import Flask, redirect, render_template, request, url_for

from utils.exceptions import DroneRouteError
from utils.web_service import (
    DEFAULT_FORM,
    MAX_DRONES,
    MAX_ORDERS,
    build_plan_view,
    parse_plan_form,
)

log = logging.getLogger("drone_planner.web")


def create_app() -> Flask:
    """Application factory (also makes the app easy to test)."""
    app = Flask(__name__)

    def page(template: str, status: int = 200, **context: Any):
        context.setdefault("max_orders", MAX_ORDERS)
        context.setdefault("max_drones", MAX_DRONES)
        return render_template(template, **context), status

    @app.get("/")
    def index():
        return page("index.html", form=dict(DEFAULT_FORM), errors=[])

    @app.route("/plan", methods=["GET", "POST"])
    def plan():
        if request.method == "GET":                 # someone opened /plan directly
            return redirect(url_for("index"))

        form: Dict[str, str] = {k: v for k, v in request.form.items()}
        plan_request, errors = parse_plan_form(form)
        if plan_request is None:
            return page("index.html", 400, form=form, errors=errors)

        try:
            view = build_plan_view(plan_request)
        except DroneRouteError as exc:              # a problem we can explain to the user
            return page("index.html", 400, form=form, errors=[str(exc)])
        except Exception:                           # a bug: log it, show a friendly message
            log.exception("Route planning failed")
            errors: List[str] = ["Something went wrong while planning the routes. "
                                 "Please try different values or restart the app."]
            return page("index.html", 500, form=form, errors=errors)

        return page("results.html", form=form, errors=[], **view)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  Drone Delivery Route Planner is running -> http://127.0.0.1:{port}\n"
          f"  (press Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
