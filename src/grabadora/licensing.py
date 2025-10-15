"""Gestión liviana de licencias mediante firmas HMAC."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

_LICENSE_HASH_ALGORITHM: Final = "sha256"


class LicenseVerificationError(RuntimeError):
    """Señala que la verificación de licencia ha fallado."""


@dataclass(slots=True)
class LicensePayload:
    """Datos que se almacenan dentro de un archivo de licencia."""

    name: str
    email: str
    issued_at: datetime
    expires_at: datetime
    product: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "issued_at": self.issued_at.astimezone(timezone.utc).isoformat(),
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat(),
            "product": self.product,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LicensePayload":
        return cls(
            name=raw["name"],
            email=raw["email"],
            issued_at=datetime.fromisoformat(raw["issued_at"]),
            expires_at=datetime.fromisoformat(raw["expires_at"]),
            product=raw["product"],
        )

    @classmethod
    def issue(
        cls,
        *,
        name: str,
        email: str,
        product: str,
        validity_days: int,
    ) -> "LicensePayload":
        if validity_days <= 0:
            raise ValueError("La validez debe ser mayor a cero días.")

        issued_at = datetime.now(tz=timezone.utc)
        expires_at = issued_at + timedelta(days=validity_days)
        return cls(name=name, email=email, issued_at=issued_at, expires_at=expires_at, product=product)


class LicenseManager:
    """Emite y verifica licencias mediante firmas HMAC."""

    def __init__(self, *, secret_key: str, product_name: str) -> None:
        if not secret_key:
            raise ValueError("La clave secreta no puede estar vacía.")
        if not product_name:
            raise ValueError("El nombre del producto no puede estar vacío.")

        self._secret_key = secret_key.encode("utf-8")
        self._product_name = product_name

    @staticmethod
    def _sign(payload: dict[str, Any], secret_key: bytes) -> str:
        message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret_key, message, getattr(hashlib, _LICENSE_HASH_ALGORITHM)).hexdigest()
        return signature

    def issue_license(self, payload: LicensePayload) -> dict[str, Any]:
        data = payload.to_dict()
        signature = self._sign(data, self._secret_key)
        data["signature"] = signature
        return data

    def issue_license_file(self, payload: LicensePayload, *, output_path: Path) -> Path:
        data = self.issue_license(payload)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path

    def verify_file(self, path: Path) -> LicensePayload:
        if not path.exists():
            raise LicenseVerificationError(f"No se encontró el archivo de licencia: {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        signature = raw.pop("signature", None)
        if not signature:
            raise LicenseVerificationError("El archivo de licencia no contiene firma.")

        expected_signature = self._sign(raw, self._secret_key)
        if not hmac.compare_digest(signature, expected_signature):
            raise LicenseVerificationError("La firma del archivo de licencia no es válida.")

        payload = LicensePayload.from_dict(raw)
        if payload.product != self._product_name:
            raise LicenseVerificationError("La licencia no corresponde a este producto.")
        if datetime.now(tz=timezone.utc) > payload.expires_at:
            raise LicenseVerificationError("La licencia ha expirado.")

        return payload

    def revoke(self, path: Path) -> None:
        """Elimina un archivo de licencia del disco."""

        try:
            path.unlink()
        except FileNotFoundError:
            raise LicenseVerificationError("El archivo de licencia ya no existe.") from None


__all__ = [
    "LicenseManager",
    "LicensePayload",
    "LicenseVerificationError",
]
