"""Interfaz gráfica sencilla para la grabadora, pensada para usuarios novatos."""

from __future__ import annotations

import queue
import threading
import wave
from pathlib import Path
from typing import Callable, Optional

try:  # pragma: no cover - la disponibilidad depende del entorno de ejecución
    import sounddevice as sd
except Exception as exc:  # pragma: no cover - solo se ejecuta si no hay backend
    sd = None
    _IMPORT_ERROR = exc
else:  # pragma: no cover - en tests no se toca el backend real
    _IMPORT_ERROR = None

try:  # pragma: no cover - depende de las librerías instaladas
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception as exc:  # pragma: no cover - entorno sin Tk
    raise RuntimeError(
        "Tkinter no está disponible en este sistema. Instálalo o usa el modo por consola con 'grabadora'."
    ) from exc

from .disclaimer import build_disclaimer
from .recorder import RecorderConfig, RecorderError

_SAMPLE_WIDTHS = {
    "int16": 2,
    "int32": 4,
    "float32": 4,
    "uint8": 1,
}


class _GuiRecorder:
    """Pequeño envoltorio para reutilizar la lógica de captura en la GUI."""

    def __init__(
        self,
        config: RecorderConfig,
        *,
        progress_callback: Callable[[int], None],
        finished_callback: Callable[[Path | None, bool], None],
        error_callback: Callable[[Exception], None],
        status_callback: Callable[[str], None],
    ) -> None:
        self.config = config
        self._progress_callback = progress_callback
        self._finished_callback = finished_callback
        self._error_callback = error_callback
        self._status_callback = status_callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: sd.RawInputStream | None = None  # type: ignore[name-defined]
        self._wave_file: wave.Wave_write | None = None
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._frames_written = 0
        self._frame_target: int | None = None
        self._output_path: Path | None = None

    def _ensure_backend(self) -> None:
        if sd is None:  # pragma: no cover - depende del sistema operativo
            raise RecorderError(
                "No se pudo inicializar el backend de audio. Instala PortAudio o revisa tus dispositivos."
            ) from _IMPORT_ERROR

    def _writer_loop(self) -> None:
        try:
            sample_width = _SAMPLE_WIDTHS.get(self.config.dtype)
            if sample_width is None:
                raise RecorderError(f"Formato de muestra no soportado: {self.config.dtype}")

            bytes_per_frame = self.config.channels * sample_width
            while True:
                if self._stop_event.is_set() and self._queue.empty():
                    break
                try:
                    chunk = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if not self._wave_file:
                    continue

                self._wave_file.writeframes(chunk)
                self._frames_written += len(chunk) // bytes_per_frame
                self._progress_callback(self._frames_written)

                if self._frame_target is not None and self._frames_written >= self._frame_target:
                    self._stop_event.set()
                    break
        except Exception as error:  # pragma: no cover - ruta excepcional
            self._error_callback(error)
            self._output_path = None
        finally:
            completed = self._frame_target is None or self._frames_written >= (self._frame_target or 0)
            output = self._output_path
            self._cleanup()
            self._finished_callback(output, not completed)
            self._output_path = None

    def start(self, output_path: Path, *, duration_seconds: Optional[float]) -> None:
        if self._thread and self._thread.is_alive():
            raise RecorderError("Ya hay una grabación en curso.")

        self._ensure_backend()

        self._output_path = output_path.expanduser().resolve()
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._frames_written = 0
        self._frame_target = (
            int(duration_seconds * self.config.sample_rate) if duration_seconds and duration_seconds > 0 else None
        )
        self._stop_event.clear()

        sample_width = _SAMPLE_WIDTHS.get(self.config.dtype)
        if sample_width is None:
            raise RecorderError(f"Formato de muestra no soportado: {self.config.dtype}")

        self._wave_file = wave.open(str(self._output_path), "wb")
        self._wave_file.setnchannels(self.config.channels)
        self._wave_file.setsampwidth(sample_width)
        self._wave_file.setframerate(self.config.sample_rate)

        bytes_per_frame = self.config.channels * sample_width

        def _callback(indata: bytes, frames: int, _time, status) -> None:  # pragma: no cover - callback externo
            if status:
                self._status_callback(str(status))
            if not self._stop_event.is_set():
                self._queue.put(bytes(indata))

        self._stream = sd.RawInputStream(  # type: ignore[call-arg]
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype=self.config.dtype,
            blocksize=self.config.block_size,
            device=self.config.device,
            callback=_callback,
        )

        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()
        self._stream.start()

        # Primer aviso de progreso para mostrar 0 segundos transcurridos.
        if bytes_per_frame:
            self._progress_callback(0)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _cleanup(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

        if self._wave_file is not None:
            try:
                self._wave_file.close()
            finally:
                self._wave_file = None

        # Vaciar cualquier dato pendiente del queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:  # pragma: no cover - protección adicional
                break


class RecorderApp(tk.Tk):
    """Aplicación Tkinter con controles sencillos."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Grabadora Intento 4")
        self.resizable(False, False)

        self._config = RecorderConfig()
        self._recorder = _GuiRecorder(
            self._config,
            progress_callback=self._on_progress,
            finished_callback=self._on_finished,
            error_callback=self._on_error,
            status_callback=self._on_status,
        )

        self._create_widgets()
        self._is_recording = False
        self._frames_recorded = 0
        self._had_error = False

    def _create_widgets(self) -> None:
        padding = {"padx": 10, "pady": 5}

        wrapper = ttk.Frame(self)
        wrapper.grid(row=0, column=0, sticky="nsew", **padding)

        disclaimer_text = build_disclaimer(
            organization="Grabadora Team",
            product_name="Grabadora Intento 4",
            contact_email="legal@example.com",
        )

        ttk.Label(wrapper, text="Descargo de responsabilidad", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )

        self.disclaimer_box = tk.Text(wrapper, width=70, height=12, wrap="word", state="normal")
        self.disclaimer_box.insert("1.0", disclaimer_text)
        self.disclaimer_box.configure(state="disabled")
        self.disclaimer_box.grid(row=1, column=0, columnspan=3, sticky="nsew")

        self.accept_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            wrapper,
            text="Confirmo que he leído y acepto el descargo de responsabilidad",
            variable=self.accept_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Separator(wrapper).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 5))

        ttk.Label(wrapper, text="Archivo de salida (WAV):").grid(row=4, column=0, sticky="w")
        self.output_var = tk.StringVar(value=str(Path.home() / "grabacion.wav"))
        ttk.Entry(wrapper, textvariable=self.output_var, width=45).grid(row=4, column=1, sticky="ew")
        ttk.Button(wrapper, text="Explorar...", command=self._choose_output).grid(row=4, column=2, sticky="e")

        ttk.Label(wrapper, text="Duración (segundos, 0 = manual)").grid(row=5, column=0, sticky="w")
        self.duration_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(wrapper, from_=0, to=3600, increment=5, textvariable=self.duration_var, width=10).grid(
            row=5, column=1, sticky="w"
        )

        self.status_var = tk.StringVar(value="Esperando para grabar")
        ttk.Label(wrapper, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )

        self.warning_var = tk.StringVar(value="")
        ttk.Label(wrapper, textvariable=self.warning_var, foreground="#b36b00").grid(
            row=7, column=0, columnspan=3, sticky="w"
        )

        button_frame = ttk.Frame(wrapper)
        button_frame.grid(row=8, column=0, columnspan=3, pady=(10, 0))

        self.start_button = ttk.Button(button_frame, text="Iniciar grabación", command=self._start_recording)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(button_frame, text="Detener", command=self._stop_recording, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=5)

    def _choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Guardar grabación",
            defaultextension=".wav",
            filetypes=(("Archivo WAV", "*.wav"), ("Todos los archivos", "*.*")),
            initialfile=Path(self.output_var.get()).name,
        )
        if filename:
            self.output_var.set(filename)

    def _start_recording(self) -> None:
        if not self.accept_var.get():
            messagebox.showwarning("Confirmación requerida", "Debes aceptar el descargo de responsabilidad antes de continuar.")
            return

        output_path = Path(self.output_var.get())
        if not output_path.suffix.lower().endswith(".wav"):
            messagebox.showerror("Ruta inválida", "El archivo de salida debe terminar en .wav")
            return

        try:
            duration = float(self.duration_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("Duración inválida", "Introduce un número válido de segundos.")
            return

        try:
            self._recorder.start(output_path, duration_seconds=duration if duration > 0 else None)
        except RecorderError as error:
            messagebox.showerror("No se puede grabar", str(error))
            return
        except Exception as error:  # pragma: no cover - errores inesperados
            messagebox.showerror("Error inesperado", str(error))
            return

        self._is_recording = True
        self._frames_recorded = 0
        self._had_error = False
        self.status_var.set("Grabando... 0.0 segundos")
        self.warning_var.set("")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

    def _stop_recording(self) -> None:
        if not self._is_recording:
            return
        self._recorder.stop()
        self.status_var.set("Finalizando grabación, espera un momento...")

    def _on_progress(self, frames: int) -> None:
        self._frames_recorded = frames
        seconds = frames / self._config.sample_rate if self._config.sample_rate else 0
        self.after(0, lambda: self.status_var.set(f"Grabando... {seconds:.1f} segundos"))

    def _on_finished(self, output: Path | None, interrupted: bool) -> None:
        def _update() -> None:
            self._is_recording = False
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            if self._had_error:
                self._had_error = False
                self.warning_var.set("")
                return
            if output and not interrupted:
                seconds = self._frames_recorded / self._config.sample_rate if self._config.sample_rate else 0
                self.status_var.set(f"Grabación guardada en {output} ({seconds:.1f} s)")
            elif output and interrupted:
                seconds = self._frames_recorded / self._config.sample_rate if self._config.sample_rate else 0
                self.status_var.set(f"Grabación detenida manualmente. Archivo guardado en {output} ({seconds:.1f} s)")
            else:
                self.status_var.set("Grabación cancelada")
            self.warning_var.set("")

        self.after(0, _update)

    def _on_error(self, error: Exception) -> None:
        def _notify() -> None:
            self._is_recording = False
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self._had_error = True
            messagebox.showerror("Error durante la grabación", str(error))
            self.status_var.set("Ocurrió un error. Inténtalo de nuevo.")
            self.warning_var.set("")

        self.after(0, _notify)

    def _on_status(self, message: str) -> None:
        self.after(0, lambda: self.warning_var.set(f"Aviso del dispositivo: {message}"))


def run() -> None:
    """Punto de entrada para scripts/entry points."""

    app = RecorderApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover - ejecución manual
    run()


__all__ = ["run", "RecorderApp"]
