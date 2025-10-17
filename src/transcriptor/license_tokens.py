"""Tools for issuing and inspecting signed license tokens."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

import jwt

from .license_service import device_fingerprint


@dataclass
class LicenseToken:
    token: str
    payload: dict


def _normalise_features(features: Sequence[str]) -> List[str]:
    return sorted({feature.strip() for feature in features if feature.strip()})


def issue_token(
    *,
    private_key_path: Path,
    holder_email: str,
    plan: str,
    features: Sequence[str],
    seats: int,
    expires_in_days: int,
    algorithm: str = "RS256",
    device_hash: str | None = None,
    grace_days: int = 7,
) -> LicenseToken:
    private_key = Path(private_key_path).read_text(encoding="utf-8")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=expires_in_days)
    payload = {
        "sub": holder_email,
        "plan": plan,
        "features": _normalise_features(features),
        "seats": int(max(1, seats)),
        "device": device_hash or device_fingerprint(),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "grace_until": int((expires_at + timedelta(days=grace_days)).timestamp()),
    }
    token = jwt.encode(payload, private_key, algorithm=algorithm)
    return LicenseToken(token=token, payload=payload)


def decode_token(token: str, public_key_path: Path, *, algorithms: Iterable[str] | None = None) -> dict:
    public_key = Path(public_key_path).read_text(encoding="utf-8")
    return jwt.decode(token, public_key, algorithms=list(algorithms or ["RS256", "ES256"]))

