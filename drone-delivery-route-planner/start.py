"""One-command launcher:   python start.py

What it does (the first run takes a minute, later runs start in seconds):
  1. creates a private virtual environment in .venv (if missing)
  2. installs the packages from requirements.txt (only when they changed)
  3. starts the Flask web app
  4. opens http://127.0.0.1:5000 in your browser

Uses only the Python standard library, so it works before anything is installed.
Options:  --port 5001   --no-browser   --no-venv (use the current Python)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".requirements.sha256"


def say(message: str) -> None:
    print(f"[start] {message}", flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def requirements_hash() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def prepare_environment() -> Path:
    """Create .venv and install requirements if needed. Returns the Python to use."""
    py = venv_python()
    if not py.exists():
        say("Creating virtual environment in .venv (one-time) ...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    if not STAMP.exists() or STAMP.read_text().strip() != requirements_hash():
        say("Installing required packages (one-time, needs internet) ...")
        subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check",
                        "-r", str(REQUIREMENTS)], check=True)
        STAMP.write_text(requirements_hash())
    return py


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def open_browser_when_ready(port: int) -> None:
    """Wait until the server answers, then open the page."""
    for _ in range(100):
        if not port_is_free(port):
            webbrowser.open(f"http://127.0.0.1:{port}")
            return
        time.sleep(0.2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up and start the Drone Delivery Route Planner website.")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    parser.add_argument("--no-venv", action="store_true", help="use the current Python instead of .venv")
    args = parser.parse_args()

    if sys.version_info < (3, 9):
        say("Python 3.9 or newer is required. Please install it from https://www.python.org/downloads/")
        return 1

    try:
        if args.no_venv:
            python = Path(sys.executable)
            if importlib.util.find_spec("flask") is None:
                say("Flask is not installed in this Python. Run:  pip install -r requirements.txt")
                return 1
        else:
            python = prepare_environment()
    except subprocess.CalledProcessError:
        say("Setup failed. Check your internet connection and try again.")
        say("Manual alternative:  python -m venv .venv  ->  activate it  ->  pip install -r requirements.txt  ->  python app.py")
        return 1

    port = args.port
    while not port_is_free(port) and port < args.port + 20:
        say(f"Port {port} is busy, trying {port + 1} ...")
        port += 1

    say(f"Starting the website -> http://127.0.0.1:{port}   (press Ctrl+C to stop)")
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()

    env = dict(os.environ, PORT=str(port))
    server = subprocess.Popen([str(python), str(ROOT / "app.py")], cwd=ROOT, env=env)
    try:
        return server.wait()
    except KeyboardInterrupt:
        say("Stopping ...")
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        return 0


if __name__ == "__main__":
    sys.exit(main())
