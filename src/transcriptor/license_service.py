"""Device-bound license verification helpers."""
from __future__ import annotations

import json
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence, Set

import jwt
from jwt import InvalidTokenError

from .config import ConfigManager, PATHS
from .logging_utils import configure_logging

logger = configure_logging()


DEFAULT_PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAMyjwljdVwwVw53ESxa0bxDMJfS2iip/
wG1+i5Ih71S5DXdhxsYhVHZiYzJFFYiZLSl8QxtOJdg6KScMsNrAXZECAwEAAQ==
-----END PUBLIC KEY-----
""".strip()


def _read_machine_guid() -> Optional[str]:
    if platform.system().lower() != "windows":
        return None
    try:
        output = subprocess.check_output(
            ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        return None
    for line in output.splitlines():
        if "MachineGuid" in line:
            parts = line.split("    ")
            if parts:
                return parts[-1].strip()
    return None


def device_fingerprint() -> str:
    """Genera una huella determinista del dispositivo."""
    components = [
        platform.node(),
        platform.machine(),
        platform.processor(),
        platform.system(),
        platform.version(),
    ]
    mac = None
    try:
        import uuid

        mac = uuid.getnode()
    except Exception:
        mac = None
    if mac:
        components.append(str(mac))
    machine_guid = _read_machine_guid()
    if machine_guid:
        components.append(machine_guid)

    joined = "|".join(component for component in components if component)
    import hashlib

    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return digest


@dataclass
class LicenseStatus:
    active: bool
    plan: str
    expires_at: Optional[datetime]
    in_grace: bool
    features: Set[str]
    reason: Optional[str] = None
    token: Optional[str] = None

    def allows(self, feature: str) -> bool:
        return feature in self.features or "*" in self.features

    def as_dict(self) -> Dict[str, object]:
        return {
            "active": self.active,
            "plan": self.plan,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "in_grace": self.in_grace,
            "features": sorted(self.features),
            "reason": self.reason,
        }


class LicenseManager:
    """Loads and verifies the device-bound license token."""

    def __init__(self, config: Optional[ConfigManager] = None, *, grace_days: int = 7) -> None:
        self.config = config or ConfigManager(PATHS.config_file)
        self.grace_days = grace_days
        self._status: Optional[LicenseStatus] = None

    # ------------------------------------------------------------------
    def _resolve_public_key(self, provided_key: Optional[str] = None) -> str:
        if provided_key and provided_key.strip():
            return provided_key.strip()
        stored = self.config.license_public_key()
        if stored:
            return stored
        env_key = os.environ.get("TRANSCRIPTOR_LICENSE_PUBLIC_KEY")
        if env_key:
            return env_key
        return DEFAULT_PUBLIC_KEY

    def _decode(self, token: str, public_key: str) -> Dict[str, object]:
        try:
            payload = jwt.decode(token, public_key, algorithms=["RS256", "ES256"], options={"require": ["exp", "sub"]})
        except InvalidTokenError as exc:
            raise ValueError(f"Licencia inválida: {exc}") from exc
        return payload

    def _validate_payload(self, payload: Dict[str, object]) -> LicenseStatus:
        now = datetime.now(timezone.utc)
        exp_raw = payload.get("exp")
        expires_at: Optional[datetime]
        if isinstance(exp_raw, (int, float)):
            expires_at = datetime.fromtimestamp(exp_raw, tz=timezone.utc)
        elif isinstance(exp_raw, str):
            expires_at = datetime.fromisoformat(exp_raw)
        else:
            expires_at = None

        device = str(payload.get("device", ""))
        plan = str(payload.get("plan", "free"))
        features_raw = payload.get("features", [])
        if isinstance(features_raw, str):
            features: Set[str] = {part.strip() for part in features_raw.split(",") if part.strip()}
        elif isinstance(features_raw, Sequence):
            features = {str(feature).strip() for feature in features_raw if str(feature).strip()}
        else:
            features = set()
        if not features:
            features = {"summary:extractivo", "export:markdown", "export:json"}

        grace_until_raw = payload.get("grace_until")
        if isinstance(grace_until_raw, (int, float)):
            grace_until = datetime.fromtimestamp(grace_until_raw, tz=timezone.utc)
        elif isinstance(grace_until_raw, str):
            try:
                grace_until = datetime.fromisoformat(grace_until_raw)
            except ValueError:
                grace_until = None
        else:
            grace_until = None

        fingerprint = device_fingerprint()
        if device and fingerprint != device:
            return LicenseStatus(
                active=False,
                plan=plan,
                expires_at=expires_at,
                in_grace=False,
                features=features,
                reason="Licencia emitida para otro dispositivo",
            )

        active = True
        in_grace = False
        if expires_at and expires_at < now:
            if grace_until and grace_until >= now:
                active = True
                in_grace = True
            else:
                active = False

        return LicenseStatus(
            active=active,
            plan=plan,
            expires_at=expires_at,
            in_grace=in_grace,
            features=features,
        )

    # ------------------------------------------------------------------
    def _load_token_from_disk(self) -> Optional[str]:
        candidates = [
            PATHS.base_dir / "licencia.json",
            PATHS.base_dir / "license.json",
            Path.cwd() / "licencia.json",
        ]
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
            token = payload.get("token")
            if isinstance(token, str) and token.strip():
                public_key = payload.get("public_key")
                if isinstance(public_key, str) and public_key.strip():
                    self.config.set_license_public_key(public_key.strip())
                logger.info("Licencia detectada en %s", candidate)
                return token.strip()
        return None

    # ------------------------------------------------------------------
    def status(self, *, force: bool = False) -> LicenseStatus:
        if self._status is not None and not force:
            return self._status

        token = self.config.license_token()
        if not token:
            token = self._load_token_from_disk()
            if token:
                self.config.set_license_token(token)

        if not token:
            self._status = LicenseStatus(
                active=False,
                plan="free",
                expires_at=None,
                in_grace=False,
                features={"summary:extractivo", "export:markdown", "export:json"},
                reason="No se encontró licencia",
            )
            return self._status

        try:
            public_key = self._resolve_public_key()
            payload = self._decode(token, public_key)
            status = self._validate_payload(payload)
            status.token = token
            if status.active:
                logger.debug("Licencia validada para plan %s", status.plan)
            else:
                logger.warning("Licencia cargada pero inactiva: %s", status.reason)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("No se pudo validar la licencia: %s", exc)
            status = LicenseStatus(
                active=False,
                plan="free",
                expires_at=None,
                in_grace=False,
                features={"summary:extractivo", "export:markdown", "export:json"},
                reason=str(exc),
            )

        self._status = status
        return status

    # ------------------------------------------------------------------
    def allows(self, feature: str) -> bool:
        return self.status().allows(feature)

    def refresh(self) -> LicenseStatus:
        self._status = None
        return self.status(force=True)

