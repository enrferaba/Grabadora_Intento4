"""Theme definitions for the Tk user interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Theme:
    name: str
    palette: Dict[str, str]

    def color(self, key: str) -> str:
        return self.palette[key]


DARK = Theme(
    name="dark",
    palette={
        "bg": "#0d1117",
        "surface": "#101623",
        "surface-alt": "#182235",
        "text": "#f0f6fc",
        "text-muted": "#94a3b8",
        "accent": "#22c55e",
        "accent-alt": "#2dd4bf",
        "danger": "#ef4444",
        "warning": "#f59e0b",
        "outline": "#1f2937",
        "selection": "#bbf7d0",
        "selection-fg": "#022c22",
    },
)

LIGHT = Theme(
    name="light",
    palette={
        "bg": "#f5f7fb",
        "surface": "#ffffff",
        "surface-alt": "#e7eef6",
        "text": "#1f2933",
        "text-muted": "#4b5563",
        "accent": "#0ea5e9",
        "accent-alt": "#2563eb",
        "danger": "#dc2626",
        "warning": "#d97706",
        "outline": "#cbd5e1",
        "selection": "#bae6fd",
        "selection-fg": "#0f172a",
    },
)

THEMES = {theme.name: theme for theme in (DARK, LIGHT)}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, DARK)
