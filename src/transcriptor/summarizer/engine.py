"""Local-first summarisation engines."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Sequence

from ..logging_utils import configure_logging
from .templates import SummaryTemplate, get_template

logger = configure_logging()


SENTENCE_REGEX = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> List[str]:
    cleaned = text.replace("\n", " ")
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [sentence.strip() for sentence in parts if sentence.strip()]


@dataclass
class ActionItem:
    owner: str
    task: str
    due: str | None = None


@dataclass
class SummaryDocument:
    template: SummaryTemplate
    mode: str
    language: str
    title: str
    summary: str
    key_points: List[str]
    actions: List[ActionItem]
    risks: List[str]
    next_steps: List[str]
    attendees: List[str] = field(default_factory=list)
    client: str | None = None
    meeting_date: str | None = None
    fallback_used: bool = False
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def as_dict(self) -> dict:
        return {
            "template": self.template.slug,
            "mode": self.mode,
            "language": self.language,
            "title": self.title,
            "summary": self.summary,
            "key_points": self.key_points,
            "actions": [action.__dict__ for action in self.actions],
            "risks": self.risks,
            "next_steps": self.next_steps,
            "attendees": self.attendees,
            "client": self.client,
            "meeting_date": self.meeting_date,
            "fallback_used": self.fallback_used,
            "generated_at": self.generated_at.isoformat(),
        }


class ExtractiveSummariser:
    """Lightweight extractive summariser that surfaces the key sentences."""

    def generate(
        self,
        *,
        text: str,
        template: SummaryTemplate,
        language: str,
        client: str | None,
        meeting_date: str | None,
    ) -> SummaryDocument:
        sentences = _split_sentences(text)
        if not sentences:
            sentences = [text.strip() or "Sin contenido"]

        headline = sentences[0]
        key_points = sentences[: min(6, len(sentences))]
        risks = [sentence for sentence in sentences if any(token in sentence.lower() for token in ("riesgo", "bloqueo", "problema"))][:3]
        next_steps = key_points[1:4] if len(key_points) > 1 else key_points

        actions = [
            ActionItem(owner="Por asignar", task=sentence, due=None)
            for sentence in key_points[:3]
        ]

        summary_text = " ".join(key_points[:3])
        return SummaryDocument(
            template=template,
            mode="extractivo",
            language=language,
            title=f"{template.title} - {client or 'Sin cliente'}",
            summary=summary_text,
            key_points=key_points,
            actions=actions,
            risks=risks,
            next_steps=next_steps,
            attendees=[],
            client=client,
            meeting_date=meeting_date,
            fallback_used=False,
        )


class LocalLLMSummariser:
    """Placeholder LLM-driven summariser with deterministic heuristics.

    In la versión empaquetada este componente se conecta al modelo cuantizado
    incluido en la instalación. Para efectos de desarrollo local generamos
    un resumen sintetizado a partir de heurísticas, manteniendo la misma
    estructura de salida requerida por las exportaciones.
    """

    def generate(
        self,
        *,
        text: str,
        template: SummaryTemplate,
        language: str,
        client: str | None,
        meeting_date: str | None,
    ) -> SummaryDocument:
        sentences = _split_sentences(text)
        if not sentences:
            sentences = [text.strip() or "Sin contenido"]

        chunk = max(1, math.ceil(len(sentences) / 8))
        highlights = [" ".join(sentences[i : i + chunk]) for i in range(0, len(sentences), chunk)]
        highlights = [part.strip() for part in highlights if part.strip()]

        key_points = highlights[:5]
        summary_text = " ".join(key_points[:3])
        risks = [sentence for sentence in sentences if "riesgo" in sentence.lower()][:3]
        if not risks and sentences:
            risks = sentences[-2:]

        actions = [
            ActionItem(owner="Equipo", task=point, due=None)
            for point in key_points[:3]
        ]
        next_steps = key_points[1:4] if len(key_points) > 1 else key_points

        attendees: List[str] = []
        attendee_pattern = re.compile(r"(participantes|asistentes):\s*(.*)", re.IGNORECASE)
        for sentence in sentences:
            match = attendee_pattern.search(sentence)
            if match:
                attendees = [name.strip() for name in re.split(r",|y", match.group(2)) if name.strip()]
                break

        return SummaryDocument(
            template=template,
            mode="redactado",
            language=language,
            title=f"{template.title} - {client or 'Resumen profesional'}",
            summary=summary_text,
            key_points=key_points,
            actions=actions,
            risks=risks,
            next_steps=next_steps,
            attendees=attendees,
            client=client,
            meeting_date=meeting_date,
            fallback_used=False,
        )


class SummaryOrchestrator:
    """Selects between redactado and extractive summaries."""

    def __init__(self) -> None:
        self.extractive = ExtractiveSummariser()
        self.redactado = LocalLLMSummariser()

    def generate(
        self,
        *,
        text: str,
        template_slug: str,
        mode: str,
        language: str,
        client: str | None,
        meeting_date: str | None,
        redactado_enabled: bool,
    ) -> SummaryDocument:
        template = get_template(template_slug)
        if mode == "redactado" and not redactado_enabled:
            mode = "extractivo"

        if mode == "redactado":
            document = self.redactado.generate(
                text=text,
                template=template,
                language=language,
                client=client,
                meeting_date=meeting_date,
            )
            document.fallback_used = False
            return document

        if mode == "literal":
            summary_text = text if len(text) < 1500 else text[:1500] + "…"
            document = SummaryDocument(
                template=template,
                mode="literal",
                language=language,
                title=f"{template.title} - {client or 'Transcripción literal'}",
                summary=summary_text,
                key_points=_split_sentences(summary_text)[:6],
                actions=[ActionItem(owner="Por confirmar", task="Revisar transcripción", due=None)],
                risks=[],
                next_steps=["Revisar el texto completo"],
                attendees=[],
                client=client,
                meeting_date=meeting_date,
                fallback_used=False,
            )
            return document

        document = self.extractive.generate(
            text=text,
            template=template,
            language=language,
            client=client,
            meeting_date=meeting_date,
        )
        if mode == "redactado":
            document.fallback_used = True
        return document

