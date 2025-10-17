"""Audio transcription services used by the backend and GUI."""
from __future__ import annotations

import gc
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Tuple

from pydub import AudioSegment

from ..config import PATHS
from ..logging_utils import configure_logging

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

    @staticmethod
    def has_cuda() -> bool:
        try:
            import torch  # type: ignore

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _create(self, name: str, device: str) -> WhisperModel:
        selected_device = device
        if selected_device == "cuda" and not self.has_cuda():
            logger.info("CUDA unavailable, falling back to CPU")
            selected_device = "cpu"
        compute_type = "int8" if selected_device == "cpu" else "float16"
        logger.info("loading model %s on %s [%s]", name, selected_device, compute_type)
        return WhisperModel(
            name,
            device=selected_device,
            compute_type=compute_type,
            download_root=str(self._models_dir),
        )

    def get(self, name: str, device: str) -> WhisperModel:
        key = f"{name}::{device}"
        if key != self._key or self._cache is None:
            self.dispose()
            self._cache = self._create(name, device)
            self._key = key
        return self._cache

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


ProgressCallback = Callable[[Optional[float], Segment], None]


class Transcriber:
    """High level transcription orchestrator."""

    def __init__(self, provider: ModelProvider, corrector: GrammarCorrector | None = None) -> None:
        self.provider = provider
        self.corrector = corrector

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
    ) -> Tuple[str, List[Segment], float]:
        model = self.provider.get(model_name, device)
        t0 = time.time()

        waveform = AudioSegment.from_file(str(audio_path))
        duration = waveform.duration_seconds or 1.0

        segments_iter, _info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
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
        return text, segments, elapsed


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

