"""System tray launcher that boots the local API and Next.js frontend."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - optional runtime dependency
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - headless fallback
    pystray = None  # type: ignore
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore

from ..constants import API_HOST, API_PORT, DEV_FRONTEND_PORT
from ..logging_utils import configure_logging

logger = configure_logging()


@dataclass
class LauncherConfig:
    host: str = API_HOST
    api_port: int = API_PORT
    auto_open: bool = True
    launch_dev_ui: bool = False


class Launcher:
    """Coordinates backend and frontend processes and exposes a tray menu."""

    def __init__(self, config: LauncherConfig | None = None) -> None:
        self.config = config or LauncherConfig()
        env_toggle = os.environ.get("TRANSCRIPTOR_LAUNCHER_DEV_UI", "0").lower() in {"1", "true", "yes", "on"}
        if env_toggle:
            self.config.launch_dev_ui = True
        self._api_proc: Optional[subprocess.Popen] = None
        self._ui_proc: Optional[subprocess.Popen] = None
        self._tray_icon: Optional[pystray.Icon] = None if pystray else None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self) -> None:
        logger.info("Iniciando launcher")
        self._start_api()
        if self.config.launch_dev_ui:
            self._start_ui()
        if self.config.auto_open:
            threading.Thread(target=self._open_browser, daemon=True).start()
        if pystray:
            self._run_tray()
        else:
            self._wait_for_processes()

    # ------------------------------------------------------------------
    def _find_available_port(self, base_port: int) -> int:
        for offset in range(3):
            candidate = base_port + (offset * 2)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind((self.config.host, candidate))
                except OSError:
                    continue
                return candidate
        return base_port

    def _start_api(self) -> None:
        if self._api_proc and self._api_proc.poll() is None:
            return
        resolved_port = self._find_available_port(self.config.api_port)
        if resolved_port != self.config.api_port:
            logger.info("Puerto %s ocupado, usando %s", self.config.api_port, resolved_port)
            self.config.api_port = resolved_port
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "transcriptor.api:app",
            "--host",
            self.config.host,
            "--port",
            str(self.config.api_port),
            "--log-level",
            "info",
        ]
        env = os.environ.copy()
        env.setdefault("TRANSCRIPTOR_LICENSE_PUBLIC_KEY", "")
        logger.info("Lanzando API: %s", " ".join(command))
        self._api_proc = subprocess.Popen(command, env=env)

    def _start_ui(self) -> None:
        ui_root = Path.cwd() / "ui-next"
        if not (ui_root / "package.json").is_file():
            logger.warning("UI Next.js no encontrada, omitiendo arranque del frontend")
            return
        if self._ui_proc and self._ui_proc.poll() is None:
            return
        npm_command = [
            "npm",
            "run",
            "dev",
            "--",
            "--hostname",
            self.config.host,
            "--port",
            str(DEV_FRONTEND_PORT),
        ]
        logger.info("Lanzando UI Next.js en %s", ui_root)
        self._ui_proc = subprocess.Popen(npm_command, cwd=str(ui_root))

    def _open_browser(self) -> None:
        time.sleep(1.0)
        url = f"http://{self.config.host}:{self.config.api_port}"
        logger.info("Abriendo navegador en %s", url)
        webbrowser.open(url)

    # ------------------------------------------------------------------
    def _run_tray(self) -> None:
        if not pystray:
            return

        icon = self._create_icon()

        def on_open(icon: pystray.Icon, _: object) -> None:
            self._open_browser()

        def on_restart(icon: pystray.Icon, _: object) -> None:
            logger.info("Reiniciando servicios")
            self.stop()
            self._start_api()
            self._start_ui()

        def on_exit(icon: pystray.Icon, _: object) -> None:
            logger.info("Saliendo del launcher")
            self.stop()
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem("Abrir", on_open),
            pystray.MenuItem("Reiniciar", on_restart),
            pystray.MenuItem("Salir", on_exit),
        )

        icon.menu = menu
        icon.run()

    def _create_icon(self) -> pystray.Icon:
        if not pystray:
            raise RuntimeError("pystray no disponible")
        image = Image.new("RGB", (64, 64), (20, 20, 20))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 56, 56), outline=(200, 80, 0), width=3)
        draw.text((18, 20), "TF", fill=(255, 255, 255))
        icon = pystray.Icon("transcriptor", image, "Transcriptor de FERIA")
        self._tray_icon = icon
        return icon

    def _wait_for_processes(self) -> None:
        try:
            while True:
                time.sleep(1.0)
                if self._api_proc and self._api_proc.poll() is not None:
                    logger.warning("API detenida, intentando reinicio")
                    self._start_api()
                if self.config.launch_dev_ui and self._ui_proc and self._ui_proc.poll() is not None:
                    logger.warning("UI detenida, intentando reinicio")
                    self._start_ui()
        except KeyboardInterrupt:
            self.stop()

    # ------------------------------------------------------------------
    def stop(self) -> None:
        with self._lock:
            for proc in (self._api_proc, self._ui_proc):
                if proc and proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            self._api_proc = None
            self._ui_proc = None


def run_launcher() -> None:
    Launcher().start()

