"""Simple HMAC based licensing helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class LicensePayload:
    holder: str
    email: str
    issued_at: str
    expires_at: str
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "holder": self.holder,
            "email": self.email,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }
        if self.note:
            data["note"] = self.note
        return data

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "LicensePayload":
        return LicensePayload(
            holder=str(payload.get("holder", "")),
            email=str(payload.get("email", "")),
            issued_at=str(payload.get("issued_at", "")),
            expires_at=str(payload.get("expires_at", "")),
            note=payload.get("note"),
        )

    def is_valid(self) -> bool:
        try:
            expiry = datetime.fromisoformat(self.expires_at)
        except Exception:
            return False
        return expiry >= datetime.utcnow()


def _mac(secret: str, payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def issue_license(
    *,
    holder: str,
    email: str,
    validity_days: int,
    secret: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    issued_at = datetime.utcnow()
    payload = LicensePayload(
        holder=holder.strip(),
        email=email.strip(),
        issued_at=issued_at.isoformat(timespec="seconds"),
        expires_at=(issued_at + timedelta(days=validity_days)).isoformat(timespec="seconds"),
        note=note.strip() if note else None,
    )
    body = payload.to_dict()
    signature = _mac(secret, body)
    return {"payload": body, "signature": signature}


def verify_license(blob: Dict[str, Any], secret: str) -> bool:
    payload = blob.get("payload")
    signature = blob.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, str):
        return False
    expected = _mac(secret, payload)
    if not hmac.compare_digest(signature, expected):
        return False
    return LicensePayload.from_dict(payload).is_valid()


def save_license(blob: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")


def load_license(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
