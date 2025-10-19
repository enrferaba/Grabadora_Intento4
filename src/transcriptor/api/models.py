"""Pydantic request/response models for the local API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"] = "ok"
    time: datetime = Field(default_factory=datetime.utcnow)
    version: str
    license: Dict[str, Any]
    cuda_available: bool = False
    vad_available: bool = False
    missing_vad_assets: List[str] = Field(default_factory=list)
    ffmpeg_path: Optional[str] = None


class TranscriptionJobResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: Optional[str]
    progress: float
    eta_seconds: Optional[float]
    created_at: datetime
    updated_at: datetime
    duration_seconds: Optional[float]
    language: Optional[str]
    device: str
    model: str
    vad: bool
    beam_size: int
    artifacts: Dict[str, Dict[str, str]]
    metadata: Dict[str, Any]
    summary_modes: List[str]


class JobsEnvelope(BaseModel):
    jobs: List[TranscriptionJobResponse]


class SummarizeRequest(BaseModel):
    job_id: str
    template: Literal["atencion", "comercial", "soporte"] = "comercial"
    mode: Literal["redactado", "extractivo", "literal"] = "redactado"
    language: Literal["es", "en"] = "es"
    client_name: Optional[str] = None
    meeting_date: Optional[str] = None


class SummaryAction(BaseModel):
    owner: str
    task: str
    due: Optional[str]


class SummaryResponse(BaseModel):
    job_id: str
    template: str
    mode: str
    fallback_used: bool = False
    generated_at: datetime
    title: str
    client: Optional[str]
    date: Optional[str]
    attendees: List[str]
    summary: str
    key_points: List[str]
    actions: List[SummaryAction]
    risks: List[str]
    next_steps: List[str]


class ExportRequest(BaseModel):
    job_id: str
    template: Literal["atencion", "comercial", "soporte"] = "comercial"
    mode: Literal["redactado", "extractivo", "literal"] = "redactado"
    format: Literal["markdown", "docx", "json"] = "markdown"
    language: Literal["es", "en"] = "es"
    client_name: Optional[str] = None
    meeting_date: Optional[str] = None


class LicenseStatusPayload(BaseModel):
    active: bool
    plan: str
    expires_at: Optional[datetime]
    in_grace: bool
    features: List[str]
    reason: Optional[str]

