"""Motor de grabación de audio eficiente basado en buffers."""

from __future__ import annotations

import contextlib
import queue
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

try:  # pragma: no cover - la importación depende del entorno
    import sounddevice as sd
except Exception as exc:  # pragma: no cover - solo se ejecuta si no hay backend
    sd = None
    _IMPORT_ERROR = exc
else:  # pragma: no cover - en tests se usa doble verificación
    _IMPORT_ERROR = None


class RecorderError(RuntimeError):
    """Error al configurar o ejecutar la captura de audio."""


@dataclass(slots=True)
class RecorderConfig:
    """Configuración avanzada para la sesión de grabación."""

    sample_rate: int = 48_000
    channels: int = 2
    dtype: str = "int16"
    block_duration_ms: int = 50
    device: int | str | None = None
    banner_lines: Iterable[str] = ()

    @property
    def block_size(self) -> int:
        return max(1, int(self.sample_rate * (self.block_duration_ms / 1000)))


_SAMPLE_WIDTHS = {
    "int16": 2,
    "int32": 4,
    "float32": 4,
    "uint8": 1,
}


class AudioRecorder:
    """Grabador optimizado que escribe el audio directamente en disco."""

    def __init__(self, config: RecorderConfig | None = None, *, console: Console | None = None) -> None:
        self.config = config or RecorderConfig()
        self.console = console or Console()

    def _ensure_backend(self) -> None:
        if sd is None:
            raise RecorderError(
                "No se pudo importar sounddevice. Instala las dependencias de audio necesarias"
            ) from _IMPORT_ERROR

    def _get_sample_width(self) -> int:
        try:
            return _SAMPLE_WIDTHS[self.config.dtype]
        except KeyError as exc:  # pragma: no cover - depende de la configuración
            raise RecorderError(f"Formato de muestra no soportado: {self.config.dtype}") from exc

    def record_to_file(
        self,
        output_path: Path,
        *,
        duration_seconds: float | None = None,
        license_text: str | None = None,
    ) -> Path:
        """Realiza una captura de audio con escritura incremental a disco."""

        self._ensure_backend()

        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sample_width = self._get_sample_width()
        frame_count_target = None
        if duration_seconds:
            frame_count_target = int(duration_seconds * self.config.sample_rate)

        if license_text:
            banner = "\n" + "\n".join(f"# {line}" for line in license_text.splitlines()) + "\n"
        else:
            banner = ""

        for line in self.config.banner_lines:
            self.console.print(line)

        if banner:
            self.console.print(banner)

        q: "queue.Queue[bytes]" = queue.Queue()

        def _callback(indata: bytes, frames: int, _time, status) -> None:  # pragma: no cover - callback externo
            if status:
                self.console.log(f"[yellow]Advertencia del backend de audio:[/yellow] {status}")
            q.put(bytes(indata))

        with contextlib.ExitStack() as stack:
            stream = sd.RawInputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=self.config.block_size,
                device=self.config.device,
                callback=_callback,
            )
            stack.enter_context(stream)
            wave_file = wave.open(str(output_path), "wb")
            stack.enter_context(contextlib.closing(wave_file))
            wave_file.setnchannels(self.config.channels)
            wave_file.setsampwidth(sample_width)
            wave_file.setframerate(self.config.sample_rate)

            bytes_per_frame = self.config.channels * sample_width
            frames_written = 0

            progress = Progress(
                TextColumn("[bold green]Grabando[/bold green]"),
                BarColumn(bar_width=None),
                TextColumn("{task.completed:,} frames"),
                TimeElapsedColumn(),
                console=self.console,
                transient=True,
            )

            task_id = progress.add_task("grabacion", total=frame_count_target or 0)
            stack.enter_context(progress)

            try:
                while True:
                    try:
                        chunk = q.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    wave_file.writeframes(chunk)
                    frames_written += len(chunk) // bytes_per_frame
                    if frame_count_target is not None:
                        progress.update(task_id, completed=min(frames_written, frame_count_target))
                        if frames_written >= frame_count_target:
                            break
                    else:
                        progress.update(task_id, completed=frames_written)
            except KeyboardInterrupt:  # pragma: no cover - interacción directa
                self.console.log("[yellow]Grabación interrumpida por el usuario.[/yellow]")
            finally:
                time.sleep(0.1)  # asegura que el backend vacíe los buffers

        self.console.log(
            f"[bold cyan]Archivo guardado en:[/bold cyan] {output_path} ({frames_written:,} frames)"
        )
        return output_path


__all__ = ["AudioRecorder", "RecorderConfig", "RecorderError"]
