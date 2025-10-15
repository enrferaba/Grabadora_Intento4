"""Utilidades para construir mensajes formales de descargo de responsabilidad."""

from __future__ import annotations

from datetime import datetime
from textwrap import dedent
from typing import Iterable

DEFAULT_POINTS: tuple[str, ...] = (
    "El usuario es el único responsable de obtener los permisos legales para grabar.",
    "El desarrollador no se hace responsable de grabaciones indebidas o su uso posterior.",
    "Las transcripciones generadas a partir del audio son responsabilidad exclusiva del usuario.",
)


def build_disclaimer(
    *,
    organization: str,
    product_name: str,
    contact_email: str | None = None,
    extra_points: Iterable[str] | None = None,
) -> str:
    """Genera un descargo de responsabilidad formal para mostrar al usuario.

    Args:
        organization: Nombre de la entidad o persona responsable de la licencia.
        product_name: Nombre comercial del producto.
        contact_email: Correo de contacto para soporte o consultas legales.
        extra_points: Puntos adicionales para extender el descargo.

    Returns:
        Cadena de texto con formato listo para mostrarse al usuario.
    """

    lines: list[str] = [
        f"{product_name.upper()} - DESCARGO DE RESPONSABILIDAD LEGAL",
        "=" * 72,
        f"Fecha de generación: {datetime.utcnow():%Y-%m-%d %H:%M UTC}",
        f"Titular de la licencia: {organization}",
        "",
        "Al continuar, usted declara que entiende y acepta los siguientes puntos:",
    ]

    bullet_points = list(DEFAULT_POINTS)
    if extra_points:
        bullet_points.extend(point.strip() for point in extra_points if point.strip())

    for idx, point in enumerate(bullet_points, start=1):
        lines.append(f"  {idx}. {point}")

    if contact_email:
        lines.extend(
            [
                "",
                "Para cualquier consulta relacionada con el uso de la aplicación,",
                f"escríbanos a: {contact_email}",
            ]
        )

    lines.append("")
    lines.append(dedent(
        """
        IMPORTANTE: La instalación y/o uso continuo de esta herramienta implica
        la aceptación íntegra de este descargo de responsabilidad. Si no está de
        acuerdo, desinstale el software inmediatamente.
        """
    ).strip())

    return "\n".join(lines)


__all__ = ["build_disclaimer", "DEFAULT_POINTS"]
