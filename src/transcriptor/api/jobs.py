"""Persistent job registry used by the local FastAPI backend."""
from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..config import PATHS


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
    """Thread-safe registry of transcription jobs with disk persistence."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or PATHS.jobs_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.RLock()
        self._load_existing()

    # ------------------------------------------------------------------
    def _manifest_path(self, job_id: str) -> Path:
        return self._storage_dir / job_id / "manifest.json"

    def _save_manifest(self, job: JobRecord) -> None:
        manifest_path = self._manifest_path(job.id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {
            "id": job.id,
            "filename": job.filename,
            "status": job.status,
            "message": job.message,
            "progress": job.progress,
            "eta_seconds": job.eta_seconds,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "duration_seconds": job.duration_seconds,
            "language": job.language,
            "device": job.device,
            "model": job.model,
            "vad": job.vad,
            "beam_size": job.beam_size,
            "artifacts": {
                key: {
                    "name": artifact.name,
                    "path": str(artifact.path),
                    "content_type": artifact.content_type,
                }
                for key, artifact in job.artifacts.items()
            },
            "metadata": job.metadata,
            "summaries": job.summaries,
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_existing(self) -> None:
        for manifest in self._storage_dir.glob("*/manifest.json"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                continue
            try:
                record = self._record_from_manifest(data)
            except Exception:
                continue
            self._jobs[record.id] = record

    def _record_from_manifest(self, data: Dict[str, Any]) -> JobRecord:
        created = self._parse_datetime(data.get("created_at"))
        updated = self._parse_datetime(data.get("updated_at"))
        record = JobRecord(
            id=str(data.get("id")),
            filename=str(data.get("filename")),
            created_at=created,
            updated_at=updated,
            status=str(data.get("status", JobStatus.QUEUED)),
            message=data.get("message"),
            progress=float(data.get("progress", 0.0) or 0.0),
            eta_seconds=data.get("eta_seconds"),
            duration_seconds=data.get("duration_seconds"),
            language=data.get("language"),
            device=str(data.get("device", "auto")),
            model=str(data.get("model", "medium")),
            vad=bool(data.get("vad", True)),
            beam_size=int(data.get("beam_size", 5) or 5),
        )
        artifacts = data.get("artifacts", {}) or {}
        for key, payload in artifacts.items():
            path = Path(payload.get("path", ""))
            if not path.exists():
                continue
            record.artifacts[key] = JobArtifact(
                name=str(payload.get("name", path.name)),
                path=path,
                content_type=str(payload.get("content_type", "application/octet-stream")),
            )
        metadata = data.get("metadata", {}) or {}
        if isinstance(metadata, dict):
            record.metadata.update(metadata)
        summaries = data.get("summaries", {}) or {}
        if isinstance(summaries, dict):
            for key, payload in summaries.items():
                if isinstance(payload, dict):
                    record.summaries[key] = payload
        return record

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.utcnow()

    def _touch(self, job: JobRecord) -> None:
        job.updated_at = datetime.utcnow()
        self._save_manifest(job)

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
            self._save_manifest(record)
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
            self._touch(job)

    def set_progress(self, job_id: str, progress: float, eta_seconds: Optional[float] = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.progress = max(0.0, min(progress, 100.0))
            job.eta_seconds = eta_seconds
            self._touch(job)

    def attach_artifact(self, job_id: str, key: str, artifact: JobArtifact) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.artifacts[key] = artifact
            self._touch(job)

    def mark_duration(self, job_id: str, duration_seconds: Optional[float]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.duration_seconds = duration_seconds
            self._touch(job)

    def add_metadata(self, job_id: str, **metadata: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.metadata.update(metadata)
            self._touch(job)

    def store_summary(self, job_id: str, mode_key: str, summary_payload: Dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.summaries[mode_key] = summary_payload
            self._touch(job)

    def summary(self, job_id: str, mode_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs[job_id]
            return job.summaries.get(mode_key)

    # ------------------------------------------------------------------
    def prune(self, *, retention_days: int) -> None:
        cutoff = time.time() - (retention_days * 86400)
        with self._lock:
            stale_ids: List[str] = []
            for job_id, job in list(self._jobs.items()):
                if job.created_at.timestamp() < cutoff:
                    stale_ids.append(job_id)
            for job_id in stale_ids:
                self._remove(job_id)

    def _remove(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        manifest = self._manifest_path(job_id)
        if manifest.exists():
            try:
                manifest.unlink()
            except OSError:
                pass
        job_dir = manifest.parent
        if job_dir.exists():
            try:
                shutil.rmtree(job_dir)
            except OSError:
                pass

    # ------------------------------------------------------------------
    def __iter__(self) -> Iterable[JobRecord]:
        return iter(self.list())
