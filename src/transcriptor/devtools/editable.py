"""Utilidades para localizar y limpiar instalaciones editables obsoletas."""
from __future__ import annotations

import json
import shutil
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse
from urllib.request import url2pathname

import site


@dataclass(slots=True)
class Artifact:
    """Representa un artefacto instalado que puede interferir con el editable actual."""

    path: Path
    kind: str
    detail: str | None = None

    def to_dict(self) -> dict[str, str]:
        data = {
            "path": str(self.path),
            "kind": self.kind,
        }
        if self.detail:
            data["detail"] = self.detail
        return data


def detect_editable_artifacts(expected_roots: Iterable[Path] | None = None) -> list[Artifact]:
    """Devuelve los artefactos instalados que no apuntan a las rutas esperadas."""

    roots = _normalise_expected_roots(expected_roots)
    artifacts: list[Artifact] = []
    for base in _candidate_directories():
        artifacts.extend(_scan_directory(base, roots))
    return artifacts


def remove_artifacts(artifacts: Sequence[Artifact]) -> list[tuple[Artifact, bool, str | None]]:
    """Elimina los artefactos proporcionados."""

    results: list[tuple[Artifact, bool, str | None]] = []
    for artifact in artifacts:
        try:
            if artifact.path.is_dir():
                shutil.rmtree(artifact.path)
            else:
                artifact.path.unlink()
        except FileNotFoundError:
            results.append((artifact, True, "Ya no existe"))
        except OSError as exc:  # pragma: no cover - dependiente de permisos del SO
            results.append((artifact, False, str(exc)))
        else:
            results.append((artifact, True, None))
    return results


# Helpers --------------------------------------------------------------------


def _normalise_expected_roots(expected: Iterable[Path] | None) -> set[Path]:
    if expected is None:
        module_path = Path(__file__).resolve()
        parents = list(module_path.parents)
        selected = parents[:4]
    else:
        selected = [Path(p) for p in expected]
    roots = {p.resolve() for p in selected if p is not None}
    return {p for p in roots if len(p.parts) > 1}


def _candidate_directories() -> list[Path]:
    bases: set[Path] = set()
    for raw in sysconfig.get_paths().values():
        if raw:
            bases.add(Path(raw))
    for raw in site.getsitepackages():
        bases.add(Path(raw))
    user_site = site.getusersitepackages()
    if user_site:
        bases.add(Path(user_site))
    return sorted({path.resolve() for path in bases if Path(path).exists()})


def _scan_directory(base: Path, roots: set[Path]) -> list[Artifact]:
    results: list[Artifact] = []
    results.extend(_scan_egg_links(base, roots))
    results.extend(_scan_pth_files(base, roots))
    results.extend(_scan_dist_info(base, roots))
    results.extend(_scan_egg_info(base))
    return results


def _scan_egg_links(base: Path, roots: set[Path]) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for entry in base.glob("transcriptor-feria*.egg-link"):
        target = _read_first_line(entry)
        target_path = _safe_path(target)
        if target_path is not None and _matches_expected(target_path, roots):
            continue
        detail = target or "(sin ruta)"
        artifacts.append(Artifact(path=entry, kind="egg-link", detail=detail))
    return artifacts


def _scan_pth_files(base: Path, roots: set[Path]) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for entry in base.glob("*.pth"):
        try:
            content = entry.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - dependiente de permisos
            continue
        if "transcriptor" not in content.lower():
            continue
        if any(str(root) in content for root in roots):
            continue
        artifacts.append(Artifact(path=entry, kind="pth", detail="contiene referencias a transcriptor"))
    return artifacts


def _scan_dist_info(base: Path, roots: set[Path]) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for entry in base.glob("transcriptor_feria-*.dist-info"):
        record = entry / "RECORD"
        direct_url = entry / "direct_url.json"
        if record.exists():
            target_path = _direct_url_path(direct_url)
            if target_path is not None and _matches_expected(target_path, roots):
                continue
            if not direct_url.exists():
                # Instalación en modo wheel estándar; no debe causar conflictos.
                continue
            detail = str(target_path) if target_path is not None else "direct_url ajeno"
        else:
            detail = "sin RECORD"
        artifacts.append(Artifact(path=entry, kind="dist-info", detail=detail))
    return artifacts


def _scan_egg_info(base: Path) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for entry in base.glob("transcriptor*-*.egg-info"):
        artifacts.append(Artifact(path=entry, kind="egg-info"))
    legacy = base / "transcriptor-feria.egg-info"
    if legacy.exists():
        artifacts.append(Artifact(path=legacy, kind="egg-info"))
    return artifacts


def _read_first_line(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - dependiente de permisos
        return None
    line = text.strip().splitlines()
    return line[0].strip() if line else None


def _safe_path(value: str | None) -> Path | None:
    if not value:
        return None
    try:
        return Path(value).expanduser().resolve()
    except OSError:  # pragma: no cover - rutas inválidas
        return None


def _direct_url_path(path: Path) -> Path | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensivo
        return None
    url = data.get("url")
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    converted = url2pathname(parsed.path)
    combined = converted
    if parsed.netloc and not converted.startswith("\\\\"):
        combined = f"//{parsed.netloc}{converted}"
    try:
        return Path(combined).resolve()
    except OSError:  # pragma: no cover - rutas inválidas
        return None


def _matches_expected(path: Path, roots: set[Path]) -> bool:
    for root in roots:
        if path == root:
            return True
        try:
            if path.is_relative_to(root):
                return True
        except ValueError:
            pass
        try:
            if root.is_relative_to(path):
                return True
        except ValueError:
            pass
    return False
