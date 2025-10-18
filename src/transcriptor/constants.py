"""Shared constants to keep host and port configuration in sync."""
from __future__ import annotations

import os
from pathlib import Path

API_HOST = os.environ.get("TRANSCRIPTOR_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("TRANSCRIPTOR_API_PORT", "4814"))
DEV_FRONTEND_PORT = int(os.environ.get("TRANSCRIPTOR_DEV_FRONTEND_PORT", "4815"))

API_ORIGIN = f"http://{API_HOST}:{API_PORT}"
DEV_FRONTEND_ORIGIN = f"http://{API_HOST}:{DEV_FRONTEND_PORT}"
DEFAULT_UI_DIST = Path(__file__).resolve().parent / "ui_static"
UI_DIST_PATH = Path(os.environ.get("TRANSCRIPTOR_UI_DIST", DEFAULT_UI_DIST)).expanduser()

__all__ = [
    "API_HOST",
    "API_PORT",
    "DEV_FRONTEND_PORT",
    "API_ORIGIN",
    "DEV_FRONTEND_ORIGIN",
    "UI_DIST_PATH",
]
