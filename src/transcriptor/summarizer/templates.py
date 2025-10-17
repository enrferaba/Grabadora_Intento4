"""Summary template definitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class SummaryTemplate:
    slug: str
    title: str
    description: str
    default_attendees_label: str
    default_actions_label: str


TEMPLATES: Dict[str, SummaryTemplate] = {
    "atencion": SummaryTemplate(
        slug="atencion",
        title="Informe de atención al cliente",
        description="Seguimiento detallado de casos de soporte y satisfacción del cliente.",
        default_attendees_label="Agentes y participantes",
        default_actions_label="Compromisos con el cliente",
    ),
    "comercial": SummaryTemplate(
        slug="comercial",
        title="Resumen de reunión comercial",
        description="Puntos clave y próximos pasos tras una reunión de venta consultiva.",
        default_attendees_label="Equipo y clientes",
        default_actions_label="Acciones comerciales",
    ),
    "soporte": SummaryTemplate(
        slug="soporte",
        title="Acta de soporte técnico",
        description="Diagnóstico técnico, acuerdos y tareas pendientes.",
        default_attendees_label="Personal técnico y contacto",
        default_actions_label="Acciones técnicas",
    ),
}


def get_template(slug: str) -> SummaryTemplate:
    try:
        return TEMPLATES[slug]
    except KeyError as exc:  # pragma: no cover - FastAPI validation already guards this
        raise ValueError(f"Plantilla desconocida: {slug}") from exc

