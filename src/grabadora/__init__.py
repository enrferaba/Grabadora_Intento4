"""Grabadora Intento 4.

Módulo principal del paquete. Proporciona acceso a utilidades de licencia,
mensajes de descargo de responsabilidad y grabación de audio optimizada.
"""

from .disclaimer import build_disclaimer
from .licensing import LicenseManager, LicensePayload, LicenseVerificationError
from .recorder import AudioRecorder, RecorderConfig, RecorderError

__all__ = [
    "AudioRecorder",
    "RecorderConfig",
    "RecorderError",
    "LicenseManager",
    "LicensePayload",
    "LicenseVerificationError",
    "build_disclaimer",
]
