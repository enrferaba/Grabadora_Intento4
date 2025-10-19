"""Audio transcription services used by the backend and GUI."""
from __future__ import annotations

import gc
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Tuple

from pydub import AudioSegment

from ..config import PATHS
from ..logging_utils import configure_logging

# Faster-Whisper enables Xet storage by default which prints noisy warnings when the
# optional dependency is missing. Disabling it keeps the logs clean while still
# falling back to the regular HTTP client when downloads are required.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

logger = configure_logging()

try:  # pragma: no cover - optional dependency
    import language_tool_python
except Exception:  # pragma: no cover
    language_tool_python = None

if PATHS.ffmpeg_executable:
    AudioSegment.converter = str(PATHS.ffmpeg_executable)

try:
    from faster_whisper import WhisperModel
except ImportError as exc:  # pragma: no cover - make failure explicit for packaging
    raise RuntimeError("faster-whisper is required to run the transcriber") from exc


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    text: str
    segments: List[Segment]
    elapsed: float
    device: str
    vad_applied: bool


class GrammarCorrector:
    """Runs LanguageTool corrections when the optional dependency is present."""

    def __init__(self, language: str = "es") -> None:
        self.language = language
        self._tool = None
        if language_tool_python is not None:
            try:
                self._tool = language_tool_python.LanguageTool(language)
            except Exception as exc:
                logger.warning("language tool initialisation failed: %s", exc)

    def correct(self, text: str) -> str:
        if not self._tool:
            return text
        try:
            return self._tool.correct(text)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("language tool correction failed: %s", exc)
            return text


class ModelProvider:
    """Caches a single Whisper model instance to avoid redundant loads."""

    def __init__(self, models_dir: Path) -> None:
        self._models_dir = models_dir
        self._cache: Optional[WhisperModel] = None
        self._key: Optional[str] = None
        self._actual_device: Optional[str] = None
        self._cuda_checked = False
        self._cuda_available = False

    @property
    def models_dir(self) -> Path:
        return self._models_dir

    def has_cuda(self) -> bool:
        if not self._cuda_checked:
            try:
                import torch  # type: ignore

                self._cuda_available = bool(torch.cuda.is_available())
            except Exception:
                self._cuda_available = False
            finally:
                self._cuda_checked = True
        return self._cuda_available

    def _mark_cuda_unavailable(self) -> None:
        self._cuda_available = False
        self._cuda_checked = True

    def _create(self, name: str, device: str) -> Tuple[WhisperModel, str]:
        selected_device = device
        if selected_device == "cuda" and not self.has_cuda():
            logger.info("CUDA unavailable, falling back to CPU")
            selected_device = "cpu"

        compute_type = "int8" if selected_device == "cpu" else "float16"
        logger.info("loading model %s on %s [%s]", name, selected_device, compute_type)
        try:
            model = WhisperModel(
                name,
                device=selected_device,
                compute_type=compute_type,
                download_root=str(self._models_dir),
            )
        except Exception as exc:
            if selected_device != "cuda":
                raise

            # When CUDA is requested but the runtime cannot initialise it (missing
            # drivers, incompatible hardware, etc.) we transparently retry on CPU
            # and mark CUDA as unavailable for the rest of the process.
            self._mark_cuda_unavailable()
            logger.warning("CUDA initialisation failed (%s); retrying on CPU", exc)
            selected_device = "cpu"
            compute_type = "int8"
            logger.info("loading model %s on cpu [%s]", name, compute_type)
            model = WhisperModel(
                name,
                device=selected_device,
                compute_type=compute_type,
                download_root=str(self._models_dir),
            )

        return model, selected_device

    def get(self, name: str, device: str) -> Tuple[WhisperModel, str]:
        key = f"{name}::{device}"
        if key != self._key or self._cache is None:
            self.dispose()
            self._cache, self._actual_device = self._create(name, device)
            self._key = key
        return self._cache, self._actual_device or device

    def dispose(self) -> None:
        if self._cache is None:
            return
        try:
            del self._cache
            gc.collect()
            try:
                import torch  # type: ignore

                torch.cuda.empty_cache()  # type: ignore[attr-defined]
            except Exception:
                pass
        finally:
            self._cache = None
            self._key = None
            self._actual_device = None

    @property
    def last_device(self) -> Optional[str]:
        return self._actual_device


ProgressCallback = Callable[[Optional[float], Segment], None]


class Transcriber:
    """High level transcription orchestrator."""

    def __init__(self, provider: ModelProvider, corrector: GrammarCorrector | None = None) -> None:
        self.provider = provider
        self.corrector = corrector
        self._vad_available, self._missing_vad_assets = self._detect_vad_assets()
        self._warned_vad_missing = False
        self._last_vad_applied = False
        self._attempted_vad_download = False

    @staticmethod
    def _detect_vad_assets(autofetch: bool = False) -> Tuple[bool, Tuple[str, ...]]:
        try:
            from faster_whisper.vad import get_assets_path, get_vad_model
        except Exception:
            return False, tuple()

        assets_path = Path(get_assets_path())
        required = ("silero_encoder_v5.onnx", "silero_decoder_v5.onnx")

        def _missing() -> Tuple[str, ...]:
            return tuple(str(assets_path / name) for name in required if not (assets_path / name).is_file())

        missing = _missing()
        if missing and autofetch:
            try:
                get_vad_model()
            except Exception as exc:  # pragma: no cover - best effort download
                logger.debug("automatic VAD download failed: %s", exc)
            else:
                missing = _missing()
        return (len(missing) == 0, missing)

    @classmethod
    def supports_vad(cls) -> bool:
        available, _ = cls._detect_vad_assets()
        return available

    def ensure_vad_assets(self) -> None:
        if self._vad_available or self._attempted_vad_download:
            return
        self._attempted_vad_download = True
        available, missing = self._detect_vad_assets(autofetch=True)
        if available and missing:
            # The detection returned no files initially but still reports a path
            logger.debug("unexpected VAD state after download: %s", missing)
        if available:
            logger.info("Silero VAD assets ready")
            self._warned_vad_missing = False
        else:
            if missing:
                logger.warning(
                    "VAD assets are still missing after attempting an automatic download: %s",
                    ", ".join(Path(item).name for item in missing),
                )
        self._vad_available = available
        self._missing_vad_assets = missing

    @property
    def vad_available(self) -> bool:
        return self._vad_available

    @property
    def last_vad_applied(self) -> bool:
        return self._last_vad_applied

    @property
    def missing_vad_assets(self) -> Tuple[str, ...]:
        return self._missing_vad_assets

    def transcribe(
        self,
        audio_path: Path,
        *,
        model_name: str,
        device: str,
        language: Optional[str],
        vad_filter: bool,
        beam_size: int,
        cancel_event: threading.Event,
        on_progress: Optional[ProgressCallback] = None,
    ) -> TranscriptionResult:
        model, actual_device = self.provider.get(model_name, device)
        t0 = time.time()

        if vad_filter:
            self.ensure_vad_assets()

        waveform = AudioSegment.from_file(str(audio_path))
        duration = waveform.duration_seconds or 1.0

        apply_vad = vad_filter and self._vad_available
        self._last_vad_applied = apply_vad
        if vad_filter and not apply_vad and not self._warned_vad_missing:
            missing = ", ".join(Path(item).name for item in self._missing_vad_assets) or "desconocidos"
            logger.warning(
                "Faltan los assets de VAD (Silero). Se ha desactivado el filtro de silencios. "
                "Inclúyelos en el empaquetado para volver a activarlo. Archivos esperados: %s",
                missing,
            )
            self._warned_vad_missing = True

        segments_iter, _info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=beam_size,
            vad_filter=apply_vad,
            word_timestamps=True,
        )

        segments: List[Segment] = []
        text_parts: List[str] = []

        for segment in segments_iter:
            if cancel_event.is_set():
                break
            seg = Segment(start=float(segment.start), end=float(segment.end), text=str(segment.text).strip())
            segments.append(seg)
            text_parts.append(seg.text)

            if on_progress:
                words: Iterable[Any] = getattr(segment, "words", [])  # type: ignore[name-defined]
                emitted = False
                for word in words or []:
                    if cancel_event.is_set():
                        break
                    end_ts = float(getattr(word, "end", segment.end) or segment.end)
                    pct = min(100.0, (end_ts / max(1e-3, duration)) * 100.0)
                    on_progress(
                        pct,
                        Segment(
                            float(getattr(word, "start", segment.start) or segment.start),
                            end_ts,
                            str(getattr(word, "word", "")) + " ",
                        ),
                    )
                    emitted = True
                if not emitted:
                    pct = min(100.0, (seg.end / max(1e-3, duration)) * 100.0)
                    on_progress(pct, Segment(seg.start, seg.end, seg.text + "\n"))
                else:
                    on_progress(None, Segment(seg.start, seg.end, "\n"))

        elapsed = time.time() - t0
        text = "\n".join(text_parts).strip()
        if self.corrector:
            text = self.corrector.correct(text)
        return TranscriptionResult(
            text=text,
            segments=segments,
            elapsed=elapsed,
            device=actual_device,
            vad_applied=apply_vad,
        )


class OutputWriter:
    @staticmethod
    def _timestamp(value: float) -> str:
        hours = int(value // 3600)
        minutes = int((value % 3600) // 60)
        seconds = int(value % 60)
        milliseconds = int((value % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def write_txt(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        logger.info("TXT saved: %s", path)

    def write_srt(self, path: Path, segments: Iterable[Segment]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for index, segment in enumerate(segments, 1):
                handle.write(
                    f"{index}\n"
                    f"{self._timestamp(segment.start)} --> {self._timestamp(segment.end)}\n"
                    f"{segment.text.strip()}\n\n"
                )
        logger.info("SRT saved: %s", path)

