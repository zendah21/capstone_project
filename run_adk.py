"""
Lightweight runner for ADK Web.

Usage:
  # set identities and API keys as needed
  #   ASSISTANT_USER_ID=<user> ASSISTANT_SESSION_ID=<session> MAPBOX_ACCESS_TOKEN=... GOOGLE_MAPS_API_KEY=...
  python run_adk.py --host 0.0.0.0 --port 8080

This wraps the existing App object at meal_planner_agent.agent:app.
"""

import argparse
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from google.adk.web import run_app  # type: ignore

from meal_planner_agent.agent import app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start ADK Web for the meal planner.")
    parser.add_argument("--host", default=os.getenv("ADK_HOST", "0.0.0.0"), help="Host to bind.")
    parser.add_argument("--port", type=int, default=int(os.getenv("ADK_PORT", "8080")), help="Port to bind.")
    return parser.parse_args()


def install_requirements() -> None:
    """
    Install project requirements before starting the server.
    If installation fails, the exception will bubble up and stop startup.
    """
    req_path = Path(__file__).parent / "requirements.txt"
    if not req_path.exists():
        return
    subprocess.check_call(
        ["pip", "install", "-r", str(req_path)],
        env=os.environ,
    )


def main() -> None:
    args = parse_args()

    # Basic logging setup: keep it simple and chatty enough for ops
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Ensure dependencies are present (idempotent if already installed)
    install_requirements()

    # Optional identities to partition DB/memory; defaults keep the app usable locally
    user_id: str = os.getenv("ASSISTANT_USER_ID", "user")
    session_id: Optional[str] = os.getenv("ASSISTANT_SESSION_ID")

    # ADK tools read these from the tool_context; fallback to env if runner doesn't set them explicitly
    os.environ["ASSISTANT_USER_ID"] = user_id
    if session_id:
        os.environ["ASSISTANT_SESSION_ID"] = session_id

    logging.info("Starting ADK Web app on %s:%s user_id=%s session_id=%s", args.host, args.port, user_id, session_id)

    # Start ADK Web serving the app
    run_app(app=app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
