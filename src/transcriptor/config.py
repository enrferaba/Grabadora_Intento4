"""Persistent configuration helpers for Transcriptor de FERIA."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

APP_NAME = "Transcriptor"


@dataclass(frozen=True)
class AppPaths:
    """Centralised filesystem locations used by the application."""

    base_dir: Path
    log_dir: Path
    log_file: Path
    config_file: Path
    models_dir: Path
    ffmpeg_executable: Optional[Path]

    @staticmethod
    def build() -> "AppPaths":
        base = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
        log_dir = base / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        packaged_models = Path(__file__).with_name("models")
        if packaged_models.is_dir() and any(packaged_models.iterdir()):
            models_dir = packaged_models
        else:
            models_dir = base / "models"
            models_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_candidate = Path(__file__).with_name("ffmpeg").joinpath("ffmpeg.exe")
        ffmpeg_executable = ffmpeg_candidate if ffmpeg_candidate.exists() else None

        return AppPaths(
            base_dir=base,
            log_dir=log_dir,
            log_file=log_dir / "app.log",
            config_file=base / "config.json",
            models_dir=models_dir,
            ffmpeg_executable=ffmpeg_executable,
        )


class ConfigManager:
    """Thin wrapper around a JSON configuration document."""

    DEFAULTS: Dict[str, Any] = {
        "folders": {},
        "typewriter_cps": 180,
        "theme": "dark",
        "disclaimer_ack_at": None,
        "license": None,
        "license_secret": None,
    }

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: Dict[str, Any] = dict(self.DEFAULTS)
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._data.update({k: data.get(k, v) for k, v in self.DEFAULTS.items()})
        except Exception:
            # When the config cannot be parsed we fall back to defaults silently.
            self._data = dict(self.DEFAULTS)

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self._data, ensure_ascii=False, indent=2)
            self._path.write_text(payload, encoding="utf-8")
        except Exception:
            # Config persistence errors are non-fatal for the UI. They are logged elsewhere.
            pass

    # ------------------------------------------------------------------
    @property
    def folders(self) -> Dict[str, str]:
        raw = self._data.get("folders", {})
        if not isinstance(raw, dict):
            self._data["folders"] = {}
            self.save()
            return {}

        valid: Dict[str, str] = {}
        changed = False
        for alias, path_str in raw.items():
            if not isinstance(alias, str):
                changed = True
                continue

            clean_alias = alias.strip()
            if not clean_alias:
                changed = True
                continue

            if clean_alias in valid and clean_alias != alias:
                changed = True
                continue

            if not isinstance(path_str, str):
                changed = True
                continue

            clean_path = path_str.strip()
            if not clean_path:
                changed = True
                continue

            try:
                normalized_path = str(Path(clean_path).expanduser())
            except Exception:
                changed = True
                continue

            if normalized_path != clean_path or clean_alias != alias:
                changed = True

            valid[clean_alias] = normalized_path

        if changed or valid != raw:
            self._data["folders"] = valid
            self.save()

        return valid

    def set_folder(self, alias: str, value: Union[str, Path]) -> None:
        alias_clean = alias.strip()
        if not alias_clean:
            raise ValueError("El nombre no puede estar vacío.")

        try:
            path = Path(value).expanduser()
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("Ruta inválida.") from exc

        folders = dict(self.folders)
        folders[alias_clean] = str(path)
        self._data["folders"] = folders
        self.save()

    def remove_folder(self, alias: str) -> None:
        alias_clean = alias.strip()
        if not alias_clean:
            return

        folders = dict(self.folders)
        if alias_clean in folders:
            folders.pop(alias_clean)
            self._data["folders"] = folders
            self.save()

    # ------------------------------------------------------------------
    def get_cps(self) -> int:
        try:
            return int(self._data.get("typewriter_cps", 180))
        except Exception:
            return 180

    def set_cps(self, cps: int) -> None:
        self._data["typewriter_cps"] = int(max(30, cps))
        self.save()

    # ------------------------------------------------------------------
    def theme(self) -> str:
        theme = str(self._data.get("theme", "dark")).lower()
        return "light" if theme == "light" else "dark"

    def set_theme(self, theme: str) -> None:
        self._data["theme"] = theme
        self.save()

    # ------------------------------------------------------------------
    def disclaimer_ack(self) -> Optional[str]:
        value = self._data.get("disclaimer_ack_at")
        return str(value) if value else None

    def set_disclaimer_ack(self, timestamp: str) -> None:
        self._data["disclaimer_ack_at"] = timestamp
        self.save()

    # ------------------------------------------------------------------
    def license_blob(self) -> Optional[Dict[str, Any]]:
        payload = self._data.get("license")
        if isinstance(payload, dict):
            return payload
        return None

    def set_license_blob(self, blob: Optional[Dict[str, Any]]) -> None:
        self._data["license"] = blob
        self.save()

    def license_secret(self) -> Optional[str]:
        encoded = self._data.get("license_secret")
        if not isinstance(encoded, str) or not encoded:
            return None
        try:
            return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
        except Exception:
            return None

    def set_license_secret(self, secret: Optional[str]) -> None:
        if secret:
            encoded = base64.b64encode(secret.encode("utf-8")).decode("ascii")
        else:
            encoded = None
        self._data["license_secret"] = encoded
        self.save()


PATHS = AppPaths.build()
