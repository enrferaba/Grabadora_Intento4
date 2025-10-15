"""Legal disclaimers and helper utilities."""
from __future__ import annotations

from datetime import datetime
from textwrap import dedent

DISCLAIMER_TEXT = dedent(
    """
    TRANScriptor de FERIA — Descargo de responsabilidad

    Esta aplicación procesa audios para generar transcripciones automáticas.
    Como licenciante, no asumo responsabilidad por el contenido de los audios,
    su procedencia o el uso que terceros hagan de las transcripciones.

    - Usa la herramienta únicamente con archivos obtenidos de manera legal y ética.
    - Informa siempre a las personas grabadas y respeta sus derechos de privacidad.
    - Verifica cada transcripción antes de distribuirla.
    - Aceptar este aviso es condición indispensable para utilizar el software.
    """
).strip()


def disclaimer_with_signature(signature: str | None) -> str:
    body = DISCLAIMER_TEXT
    if signature:
        body += f"\n\nLicencia verificada: {signature}"
    return body


def timestamp() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
