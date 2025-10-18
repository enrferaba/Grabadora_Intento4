"""Backward compatible shim for legacy imports.

This module preserves the historical ``transcriptor.transcription.transcription``
path by re-exporting the public API from the new ``engine`` module. Once all
callers depend on the package layout introduced in vNext, this shim can be
removed safely.
"""
from __future__ import annotations

from .engine import *  # noqa: F401,F403

__all__ = [
    "GrammarCorrector",
    "ModelProvider",
    "OutputWriter",
    "Segment",
    "Transcriber",
]
