"""In-memory job registry used by the local FastAPI backend."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class JobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobArtifact:
    name: str
    path: Path
    content_type: str


@dataclass
class JobRecord:
    id: str
    filename: str
    created_at: datetime
    updated_at: datetime
    status: str = JobStatus.QUEUED
    message: Optional[str] = None
    progress: float = 0.0
    eta_seconds: Optional[float] = None
    duration_seconds: Optional[float] = None
    language: Optional[str] = None
    device: str = "auto"
    model: str = "medium"
    vad: bool = True
    beam_size: int = 5
    artifacts: Dict[str, JobArtifact] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    summaries: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status,
            "message": self.message,
            "progress": round(self.progress, 2),
            "eta_seconds": self.eta_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "device": self.device,
            "model": self.model,
            "vad": self.vad,
            "beam_size": self.beam_size,
            "artifacts": {key: {"name": art.name, "content_type": art.content_type} for key, art in self.artifacts.items()},
            "metadata": self.metadata,
            "summary_modes": list(self.summaries.keys()),
        }


class JobStore:
    """Thread-safe registry of transcription jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    def create(
        self,
        *,
        filename: str,
        model: str,
        device: str,
        vad: bool,
        beam_size: int,
        language: Optional[str],
    ) -> JobRecord:
        job_id = uuid.uuid4().hex
        now = datetime.utcnow()
        record = JobRecord(
            id=job_id,
            filename=filename,
            created_at=now,
            updated_at=now,
            status=JobStatus.QUEUED,
            language=language,
            device=device,
            model=model,
            vad=vad,
            beam_size=beam_size,
        )
        with self._lock:
            self._jobs[job_id] = record
        return record

    # ------------------------------------------------------------------
    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    # ------------------------------------------------------------------
    def list(self) -> List[JobRecord]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    # ------------------------------------------------------------------
    def set_status(self, job_id: str, status: str, *, message: Optional[str] = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = status
            job.message = message
            job.updated_at = datetime.utcnow()

    def set_progress(self, job_id: str, progress: float, eta_seconds: Optional[float] = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.progress = max(0.0, min(progress, 100.0))
            job.eta_seconds = eta_seconds
            job.updated_at = datetime.utcnow()

    def attach_artifact(self, job_id: str, key: str, artifact: JobArtifact) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.artifacts[key] = artifact
            job.updated_at = datetime.utcnow()

    def mark_duration(self, job_id: str, duration_seconds: Optional[float]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.duration_seconds = duration_seconds
            job.updated_at = datetime.utcnow()

    def add_metadata(self, job_id: str, **metadata: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.metadata.update(metadata)
            job.updated_at = datetime.utcnow()

    def store_summary(self, job_id: str, mode_key: str, summary_payload: Dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.summaries[mode_key] = summary_payload
            job.updated_at = datetime.utcnow()

    def summary(self, job_id: str, mode_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs[job_id]
            return job.summaries.get(mode_key)

    # ------------------------------------------------------------------
    def prune(self, *, retention_days: int) -> None:
        cutoff = time.time() - (retention_days * 86400)
        with self._lock:
            stale_ids: List[str] = []
            for job_id, job in self._jobs.items():
                if job.created_at.timestamp() < cutoff:
                    stale_ids.append(job_id)
            for job_id in stale_ids:
                self._jobs.pop(job_id, None)

    # ------------------------------------------------------------------
    def __iter__(self) -> Iterable[JobRecord]:
        return iter(self.list())

