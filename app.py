#!/usr/bin/env python3
"""Serve the sales-finder webpage and provide an API to trigger a search.
Optional: run search automatically on a schedule (agentic automation).
"""
import os
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="docs", static_url_path="")


def _auto_search_loop():
    """Background loop: run search every N hours."""
    interval_hours = float(os.environ.get("AUTO_SEARCH_INTERVAL_HOURS", "6"))
    interval_secs = max(60, interval_hours * 3600)
    while True:
        time.sleep(interval_secs)
        try:
            from scripts.run_search import run_search_api
            result = run_search_api()
            if result.get("ok"):
                print(f"[auto-search] Added run {result.get('run_id')} ({result.get('findings_count')} findings)")
            else:
                print(f"[auto-search] No results: {result.get('error', '')}")
        except Exception as e:
            print(f"[auto-search] Error: {e}")


def _start_auto_search():
    """Start the agentic automated search in a daemon thread if enabled."""
    if os.environ.get("ENABLE_AUTO_SEARCH", "").lower() in ("1", "true", "yes"):
        interval = os.environ.get("AUTO_SEARCH_INTERVAL_HOURS", "6")
        thread = threading.Thread(target=_auto_search_loop, daemon=True)
        thread.start()
        print(f"[auto-search] Started: running every {interval} hour(s)")


@app.route("/")
def index():
    return send_from_directory("docs", "index.html")


@app.route("/data/<path:path>")
def data(path):
    return send_from_directory("data", path)


@app.route("/api/run-search", methods=["POST"])
def run_search():
    from scripts.run_search import run_search_api
    result = run_search_api()
    return jsonify(result)


@app.route("/api/status")
def status():
    """Return whether automated search is enabled (for the UI)."""
    enabled = os.environ.get("ENABLE_AUTO_SEARCH", "").lower() in ("1", "true", "yes")
    interval = os.environ.get("AUTO_SEARCH_INTERVAL_HOURS", "6")
    return jsonify({"auto_search_enabled": enabled, "auto_search_interval_hours": interval})


if __name__ == "__main__":
    _start_auto_search()
    port = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=False)
