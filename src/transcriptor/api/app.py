"""FastAPI backend exposing local transcription and summarisation services."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from starlette import status

from .. import __version__
from ..config import ConfigManager, PATHS
from ..license_service import LicenseManager
from ..logging_utils import configure_logging
from ..transcription import GrammarCorrector, ModelProvider, OutputWriter, Transcriber
from ..transcription import Segment
from .jobs import JobArtifact, JobStatus, JobStore
from .models import (
    ExportRequest,
    HealthResponse,
    JobsEnvelope,
    LicenseStatusPayload,
    SummarizeRequest,
    SummaryResponse,
    TranscriptionJobResponse,
)
from ..summarizer import ActionItem, SummaryDocument, SummaryOrchestrator, export_document, get_template


logger = configure_logging()


class BackendContext:
    """Shared dependencies for the FastAPI application."""

    def __init__(self) -> None:
        self.config = ConfigManager(PATHS.config_file)
        self.license = LicenseManager(self.config)
        self.jobs = JobStore()
        self.orchestrator = SummaryOrchestrator()
        self.model_provider = ModelProvider(PATHS.models_dir)
        self.corrector = GrammarCorrector("es")
        self.transcriber = Transcriber(self.model_provider, self.corrector)
        self.writer = OutputWriter()

    def device_for(self, device: str) -> str:
        if device not in {"cpu", "cuda", "auto"}:
            return "cpu"
        if device == "auto":
            return "cuda" if self.model_provider.has_cuda() else "cpu"
        return device


CONTEXT = BackendContext()


def create_app() -> FastAPI:
    app = FastAPI(title="Transcriptor de FERIA", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://localhost:4815", "http://127.0.0.1"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        status_payload = CONTEXT.license.status().as_dict()
        return HealthResponse(status="ok", time=datetime.utcnow(), version=__version__, license=status_payload)

    # ------------------------------------------------------------------
    async def _persist_upload(job_id: str, upload: UploadFile) -> Path:
        job_dir = PATHS.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(upload.filename or "audio").suffix or ".bin"
        path = job_dir / f"entrada{suffix}"
        with path.open("wb") as target:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
        await upload.close()
        return path

    async def _run_transcription(job_id: str, audio_path: Path, options: Dict[str, Any]) -> None:
        CONTEXT.jobs.set_status(job_id, JobStatus.PROCESSING, message="Procesando")
        start = time.monotonic()
        cancel_event = threading.Event()

        def _on_progress(percent: float | None, segment: Segment) -> None:
            if percent is None:
                return
            elapsed = max(0.1, time.monotonic() - start)
            eta = None
            if percent > 0:
                total_estimate = elapsed / (percent / 100.0)
                eta = max(0.0, total_estimate - elapsed)
            CONTEXT.jobs.set_progress(job_id, percent, eta_seconds=eta)

        try:
            text, segments, elapsed = await asyncio.to_thread(
                CONTEXT.transcriber.transcribe,
                audio_path,
                model_name=options["model"],
                device=options["device"],
                language=options.get("language"),
                vad_filter=options.get("vad", True),
                beam_size=options.get("beam_size", 5),
                cancel_event=cancel_event,
                on_progress=_on_progress,
            )

            CONTEXT.jobs.set_progress(job_id, 100.0, eta_seconds=0.0)
            duration = segments[-1].end if segments else None
            CONTEXT.jobs.mark_duration(job_id, duration)
            CONTEXT.jobs.add_metadata(job_id, elapsed_seconds=elapsed)

            job_dir = PATHS.jobs_dir / job_id
            transcript_path = job_dir / "transcripcion.txt"
            captions_path = job_dir / "subtitulos.srt"
            segments_path = job_dir / "segmentos.json"

            CONTEXT.writer.write_txt(transcript_path, text)
            CONTEXT.writer.write_srt(captions_path, segments)
            segments_payload = [
                {"start": segment.start, "end": segment.end, "text": segment.text}
                for segment in segments
            ]
            segments_path.write_text(json.dumps(segments_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            CONTEXT.jobs.attach_artifact(
                job_id,
                "transcript",
                JobArtifact(name="Transcripción", path=transcript_path, content_type="text/plain"),
            )
            CONTEXT.jobs.attach_artifact(
                job_id,
                "captions",
                JobArtifact(name="Subtítulos", path=captions_path, content_type="application/x-subrip"),
            )
            CONTEXT.jobs.attach_artifact(
                job_id,
                "segments",
                JobArtifact(name="Segmentos", path=segments_path, content_type="application/json"),
            )

            CONTEXT.jobs.set_status(job_id, JobStatus.COMPLETED, message="Transcripción lista")
        except Exception as exc:  # pragma: no cover - runtime safeguard
            logger.exception("Error transcribiendo %s", audio_path)
            CONTEXT.jobs.set_status(job_id, JobStatus.FAILED, message=str(exc))
        finally:
            try:
                audio_path.unlink()
            except OSError:
                pass

    @app.post("/transcribe", response_model=TranscriptionJobResponse, status_code=status.HTTP_201_CREATED)
    async def transcribe(
        background: BackgroundTasks,
        file: UploadFile = File(...),
        model: str = Form("medium"),
        device: str = Form("auto"),
        vad: bool = Form(True),
        beam_size: int = Form(5),
        language: str | None = Form(None),
    ) -> TranscriptionJobResponse:
        resolved_device = CONTEXT.device_for(device)
        job = CONTEXT.jobs.create(
            filename=file.filename or "archivo",
            model=model,
            device=resolved_device,
            vad=vad,
            beam_size=beam_size,
            language=language,
        )
        CONTEXT.jobs.prune(retention_days=CONTEXT.config.retention_days())
        audio_path = await _persist_upload(job.id, file)
        background.add_task(_run_transcription, job.id, audio_path, {
            "model": model,
            "device": resolved_device,
            "vad": vad,
            "beam_size": beam_size,
            "language": language,
        })
        return TranscriptionJobResponse(**job.as_dict())

    @app.get("/jobs", response_model=JobsEnvelope)
    async def list_jobs() -> JobsEnvelope:
        CONTEXT.jobs.prune(retention_days=CONTEXT.config.retention_days())
        records = [TranscriptionJobResponse(**job.as_dict()) for job in CONTEXT.jobs.list()]
        return JobsEnvelope(jobs=records)

    @app.get("/jobs/{job_id}", response_model=TranscriptionJobResponse)
    async def job_detail(job_id: str) -> TranscriptionJobResponse:
        job = CONTEXT.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado")
        return TranscriptionJobResponse(**job.as_dict())

    @app.get("/files/{job_id}/{artifact}")
    async def download(job_id: str, artifact: str) -> FileResponse:
        job = CONTEXT.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado")
        if artifact not in job.artifacts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no disponible")
        item = job.artifacts[artifact]
        return FileResponse(item.path, media_type=item.content_type, filename=item.path.name)

    @app.post("/summarize", response_model=SummaryResponse)
    async def summarize(request: SummarizeRequest) -> SummaryResponse:
        job = CONTEXT.jobs.get(request.job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado")
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La transcripción aún no ha finalizado")

        transcript_artifact = job.artifacts.get("transcript")
        if not transcript_artifact:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay transcripción disponible")

        cache_key = f"{request.mode}:{request.template}:{request.language}:{request.client_name}:{request.meeting_date}"
        cached = CONTEXT.jobs.summary(job.id, cache_key)
        if cached:
            response_payload = {k: v for k, v in cached.items() if k != "language"}
            return SummaryResponse(**response_payload)

        text = transcript_artifact.path.read_text(encoding="utf-8")
        license_status = CONTEXT.license.status()
        allow_redactado = license_status.allows("summary:redactado")
        document = CONTEXT.orchestrator.generate(
            text=text,
            template_slug=request.template,
            mode=request.mode,
            language=request.language,
            client=request.client_name,
            meeting_date=request.meeting_date,
            redactado_enabled=allow_redactado,
        )
        response_payload = _summary_to_response(job.id, document)
        cache_payload = dict(response_payload)
        cache_payload["language"] = document.language
        CONTEXT.jobs.store_summary(job.id, cache_key, cache_payload)
        return SummaryResponse(**response_payload)

    def _summary_to_response(job_id: str, document: SummaryDocument) -> Dict[str, Any]:
        return {
            "job_id": job_id,
            "template": document.template.slug,
            "mode": document.mode,
            "fallback_used": document.fallback_used,
            "generated_at": document.generated_at,
            "title": document.title,
            "client": document.client,
            "date": document.meeting_date,
            "attendees": document.attendees,
            "summary": document.summary,
            "key_points": document.key_points,
            "actions": [
                {"owner": action.owner, "task": action.task, "due": action.due}
                for action in document.actions
            ],
            "risks": document.risks,
            "next_steps": document.next_steps,
            "language": document.language,
        }

    @app.post("/export")
    async def export_summary(request: ExportRequest) -> StreamingResponse:
        job = CONTEXT.jobs.get(request.job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado")

        transcript_artifact = job.artifacts.get("transcript")
        if not transcript_artifact:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay transcripción disponible")

        cache_key = f"{request.mode}:{request.template}:{request.language}:{request.client_name}:{request.meeting_date}"
        cached = CONTEXT.jobs.summary(job.id, cache_key)
        if cached:
            document = _payload_to_document(cached)
        else:
            text = transcript_artifact.path.read_text(encoding="utf-8")
            license_status = CONTEXT.license.status()
            allow_redactado = license_status.allows("summary:redactado")
            document = CONTEXT.orchestrator.generate(
                text=text,
                template_slug=request.template,
                mode=request.mode,
                language=request.language,
                client=request.client_name,
                meeting_date=request.meeting_date,
                redactado_enabled=allow_redactado,
            )
            cache_payload = _summary_to_response(job.id, document)
            cache_payload["language"] = document.language
            CONTEXT.jobs.store_summary(job.id, cache_key, cache_payload)

        content, content_type = export_document(document, request.format)
        filename = f"{request.template}-{request.mode}.{_extension_for(request.format)}"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(iter([content]), media_type=content_type, headers=headers)

    def _extension_for(fmt: str) -> str:
        return {
            "markdown": "md",
            "json": "json",
            "docx": "docx",
        }[fmt]

    def _payload_to_document(payload: Dict[str, Any]) -> SummaryDocument:
        template = get_template(payload["template"])
        generated_at = payload["generated_at"]
        if isinstance(generated_at, str):
            generated_at_dt = datetime.fromisoformat(generated_at)
        else:
            generated_at_dt = generated_at
        actions = []
        for item in payload["actions"]:
            if hasattr(item, "dict"):
                data = item.dict()
            else:
                data = dict(item)
            actions.append(ActionItem(owner=data.get("owner", ""), task=data.get("task", ""), due=data.get("due")))
        return SummaryDocument(
            template=template,
            mode=payload["mode"],
            language=payload.get("language", "es"),
            title=payload["title"],
            summary=payload["summary"],
            key_points=list(payload["key_points"]),
            actions=actions,
            risks=list(payload["risks"]),
            next_steps=list(payload["next_steps"]),
            attendees=list(payload["attendees"]),
            client=payload.get("client"),
            meeting_date=payload.get("date"),
            fallback_used=payload.get("fallback_used", False),
            generated_at=generated_at_dt,
        )

    @app.get("/license/status", response_model=LicenseStatusPayload)
    async def license_status() -> LicenseStatusPayload:
        status_payload = CONTEXT.license.status().as_dict()
        return LicenseStatusPayload(**status_payload)

    return app


app = create_app()

