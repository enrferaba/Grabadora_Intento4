"""Shared constants to keep host and port configuration in sync."""
from __future__ import annotations

API_HOST = "127.0.0.1"
API_PORT = 4814
FRONTEND_PORT = 4815

API_ORIGIN = f"http://{API_HOST}:{API_PORT}"
FRONTEND_ORIGIN = f"http://{API_HOST}:{FRONTEND_PORT}"

__all__ = [
    "API_HOST",
    "API_PORT",
    "FRONTEND_PORT",
    "API_ORIGIN",
    "FRONTEND_ORIGIN",
]

