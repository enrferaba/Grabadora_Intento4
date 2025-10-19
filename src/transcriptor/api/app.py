"""FastAPI backend exposing local transcription and summarisation services."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import platform
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette import status

from pydub.exceptions import CouldntDecodeError

from .. import __version__
from ..config import ConfigManager, PATHS
from ..constants import UI_DIST_PATH
from ..license_service import LicenseManager
from ..logging_utils import configure_logging
from ..transcription import (
    GrammarCorrector,
    ModelProvider,
    OutputWriter,
    Segment,
    Transcriber,
)
from ..summarizer import ActionItem, SummaryDocument, SummaryOrchestrator, export_document, get_template
from ._selftest_audio import SELFTEST_WAV_BASE64
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


logger = configure_logging()


DOCS_ENABLED = os.environ.get("TRANSCRIPTOR_DOCS", "0").lower() in {"1", "true", "yes", "on"}
DIAG_TOKEN = os.environ.get("TRANSCRIPTOR_DIAG_TOKEN")
ALLOWED_UPLOAD_SUFFIXES = {
    ".aac",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
    ".wma",
}


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
        # Intenta preparar los assets de VAD al iniciar el backend para evitar sorpresas
        self.transcriber.ensure_vad_assets()

    def device_for(self, device: str) -> str:
        if device not in {"cpu", "cuda", "auto"}:
            return "cpu"
        if device == "auto":
            return "cuda" if self.model_provider.has_cuda() else "cpu"
        return device


CONTEXT = BackendContext()


def _require_diag_token(request: Request) -> None:
    if not DIAG_TOKEN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnóstico deshabilitado")
    header = request.headers.get("Authorization") or request.headers.get("X-Transcriptor-Diag")
    if not header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de diagnóstico requerido")
    token = header.replace("Bearer ", "").strip()
    if token != DIAG_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de diagnóstico inválido")


def _diagnostic_snapshot() -> Dict[str, Any]:
    license_status = CONTEXT.license.status().as_dict()
    models_dir = CONTEXT.model_provider.models_dir
    available_models: Iterable[str] = []
    if models_dir.is_dir():
        available_models = sorted({candidate.parent.name for candidate in models_dir.glob("*/model.bin")})
    jobs_snapshot = CONTEXT.jobs.list()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "version": __version__,
        "python": sys.version,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "paths": {
            "base": str(PATHS.base_dir),
            "jobs": str(PATHS.jobs_dir),
            "logs": str(PATHS.log_dir),
            "diagnostics": str(PATHS.diagnostics_dir),
            "models": str(models_dir),
        },
        "license": license_status,
        "hardware": {
            "cuda": CONTEXT.model_provider.has_cuda(),
            "vad_assets": CONTEXT.transcriber.vad_available,
            "ffmpeg": str(PATHS.ffmpeg_executable) if PATHS.ffmpeg_executable else None,
        },
        "jobs": {
            "total": len(jobs_snapshot),
            "failed": sum(1 for job in jobs_snapshot if job.status == JobStatus.FAILED),
        },
        "solo_local": True,
        "models_present": list(available_models),
    }


def _decode_selftest_audio() -> Path:
    target = PATHS.diagnostics_dir / "selftest.wav"
    if not target.exists():
        data = base64.b64decode(SELFTEST_WAV_BASE64)
        target.write_bytes(data)
    return target


def _run_selftest(model_name: str | None = None) -> Dict[str, Any]:
    models_dir = CONTEXT.model_provider.models_dir
    if model_name is None:
        candidates = [folder.name for folder in models_dir.iterdir() if (folder / "model.bin").exists()]
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail="No hay modelos descargados. Descarga uno antes de ejecutar el autodiagnóstico.",
            )
        model_name = sorted(candidates)[0]

    audio_path = _decode_selftest_audio()
    cancel_event = threading.Event()
    result = CONTEXT.transcriber.transcribe(
        audio_path,
        model_name=model_name,
        device=CONTEXT.device_for("auto"),
        language="es",
        vad_filter=True,
        beam_size=1,
        cancel_event=cancel_event,
    )
    duration = result.segments[-1].end if result.segments else 0.0
    return {
        "model": model_name,
        "elapsed": result.elapsed,
        "duration": duration,
        "text": result.text.strip(),
        "device": result.device,
        "vad_applied": result.vad_applied,
    }


def create_app() -> FastAPI:
    openapi_url = "/openapi.json" if DOCS_ENABLED else None
    docs_url = "/docs" if DOCS_ENABLED else None
    app = FastAPI(title="Transcriptor de FERIA", version=__version__, openapi_url=openapi_url, docs_url=docs_url, redoc_url=None)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        status_payload = CONTEXT.license.status().as_dict()
        cuda_available = CONTEXT.model_provider.has_cuda()
        vad_available = CONTEXT.transcriber.vad_available
        degraded = (not cuda_available) or (not vad_available)
        return HealthResponse(
            status="degraded" if degraded else "ok",
            time=datetime.utcnow(),
            version=__version__,
            license=status_payload,
            cuda_available=cuda_available,
            vad_available=vad_available,
            missing_vad_assets=list(CONTEXT.transcriber.missing_vad_assets),
            ffmpeg_path=str(PATHS.ffmpeg_executable) if PATHS.ffmpeg_executable else None,
        )

    # ------------------------------------------------------------------
    def _normalise_suffix(filename: str | None) -> str:
        if not filename:
            return ".wav"
        suffix = Path(filename).suffix.lower()
        if suffix in ALLOWED_UPLOAD_SUFFIXES:
            return suffix
        return ".wav"

    async def _persist_upload(job_id: str, upload: UploadFile) -> Path:
        job_dir = PATHS.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        content_type = (upload.content_type or "").lower()
        if content_type and not (
            content_type.startswith("audio/")
            or content_type.startswith("video/")
            or content_type in {"application/octet-stream"}
        ):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Tipo no soportado: {upload.content_type}",
            )

        suffix = _normalise_suffix(upload.filename)
        path = job_dir / f"entrada{suffix}"
        with path.open("wb") as target:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
        await upload.close()
        size = path.stat().st_size
        if size == 0:
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo subido está vacío")
        with path.open("rb") as source:
            sample = source.read(512)
        if size < 128 or sample.lstrip().startswith((b"<!", b"<html", b"{", b"[")):
            path.unlink(missing_ok=True)
            snippet = sample[:64]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Contenido no válido (primeros bytes: {snippet!r})",
            )
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
            result = await asyncio.to_thread(
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

            text = result.text
            segments = result.segments
            elapsed = result.elapsed

            CONTEXT.jobs.set_progress(job_id, 100.0, eta_seconds=0.0)
            duration = segments[-1].end if segments else None
            CONTEXT.jobs.mark_duration(job_id, duration)
            metadata: Dict[str, Any] = {
                "elapsed_seconds": elapsed,
                "actual_device": result.device,
                "vad_applied": result.vad_applied,
            }
            if options.get("vad", True) and not result.vad_applied:
                metadata["vad_reason"] = "missing_vad_assets"
                metadata["missing_vad_assets"] = list(CONTEXT.transcriber.missing_vad_assets)
            CONTEXT.jobs.add_metadata(job_id, **metadata)

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
        except CouldntDecodeError as exc:  # pragma: no cover - runtime safeguard
            logger.warning("No se pudo decodificar el audio %s: %s", audio_path, exc)
            CONTEXT.jobs.set_status(
                job_id,
                JobStatus.FAILED,
                message="No se pudo leer el audio. Comprueba que el archivo sea un formato compatible.",
            )
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
        requested_device = device
        resolved_device = CONTEXT.device_for(device)
        requested_vad = vad
        effective_vad = vad and CONTEXT.transcriber.vad_available
        job = CONTEXT.jobs.create(
            filename=file.filename or "archivo",
            model=model,
            device=resolved_device,
            vad=effective_vad,
            beam_size=beam_size,
            language=language,
        )
        CONTEXT.jobs.prune(retention_days=CONTEXT.config.retention_days())
        audio_path = await _persist_upload(job.id, file)
        metadata: Dict[str, Any] = {
            "requested_device": requested_device,
            "requested_vad": requested_vad,
        }
        if requested_device != resolved_device:
            metadata["device_warning"] = "CUDA no disponible; se utilizará CPU"
        if requested_vad and not effective_vad:
            metadata["vad_warning"] = (
                "Faltan los assets de VAD (Silero). El filtrado de silencios se desactivó automáticamente."
            )
        if metadata:
            CONTEXT.jobs.add_metadata(job.id, **metadata)

        background.add_task(
            _run_transcription,
            job.id,
            audio_path,
            {
                "model": model,
                "device": resolved_device,
                "vad": effective_vad,
                "beam_size": beam_size,
                "language": language,
            },
        )
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

    @app.get("/__diag")
    async def diagnostics(request: Request) -> Dict[str, Any]:
        _require_diag_token(request)
        return _diagnostic_snapshot()

    @app.post("/__selftest")
    async def selftest(request: Request) -> Dict[str, Any]:
        _require_diag_token(request)
        content_type = request.headers.get("content-type", "").lower()
        body = await request.json() if content_type.startswith("application/json") else {}
        model_name = body.get("model") if isinstance(body, dict) else None
        result = await asyncio.to_thread(_run_selftest, model_name)
        return {"status": "ok", "result": result}

    @app.post("/__doctor")
    async def doctor(request: Request) -> Dict[str, Any]:
        _require_diag_token(request)
        snapshot = _diagnostic_snapshot()
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        PATHS.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = PATHS.diagnostics_dir / f"doctor-{timestamp}.zip"
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("system.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
            if PATHS.config_file.exists():
                archive.write(PATHS.config_file, arcname="config.json")
            if PATHS.log_file.exists():
                archive.write(PATHS.log_file, arcname="logs/app.log")
            models_manifest = {
                "models": [folder.name for folder in CONTEXT.model_provider.models_dir.iterdir() if folder.is_dir()],
            }
            archive.writestr("models_manifest.json", json.dumps(models_manifest, ensure_ascii=False, indent=2))
            failed_jobs = [job for job in CONTEXT.jobs.list() if job.status == JobStatus.FAILED]
            if failed_jobs:
                latest = failed_jobs[0]
                archive.writestr(
                    "last_failed_job.json",
                    json.dumps(latest.as_dict(), ensure_ascii=False, default=str, indent=2),
                )
        return {"status": "ok", "bundle": str(bundle_path)}

    if UI_DIST_PATH.is_dir() and any(UI_DIST_PATH.iterdir()):
        app.mount(
            "/",
            StaticFiles(directory=str(UI_DIST_PATH), html=True),
            name="frontend",
        )
    else:
        @app.get("/", response_class=HTMLResponse)
        async def placeholder() -> HTMLResponse:
            return HTMLResponse(
                """<html><body style='font-family: sans-serif; padding: 2rem;'>"
                "<h1>Transcriptor de FERIA</h1><p>Compila la UI con <code>npm run build && npx next export</code> "
                "y establece TRANSCRIPTOR_UI_DIST apuntando a la carpeta exportada.</p></body></html>"""
            )

    return app


app = create_app()

