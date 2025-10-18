"""Limpia instalaciones editables antiguas de transcriptor-feria."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transcriptor.devtools import Artifact, detect_editable_artifacts, remove_artifacts  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Elimina los artefactos detectados en lugar de solo listarlos.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Muestra la salida en formato JSON (ignora --apply).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    expected_roots = {REPO_ROOT.resolve(), SRC_DIR.resolve()}
    artifacts = detect_editable_artifacts(expected_roots)

    if args.json:
        payload = [artifact.to_dict() for artifact in artifacts]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if not artifacts:
        print("No se encontraron restos de instalaciones editables anteriores.")
        return 0

    print("Se detectaron artefactos que apuntan a instalaciones antiguas:\n")
    for artifact in artifacts:
        detail = f" ({artifact.detail})" if artifact.detail else ""
        print(f" - {artifact.kind}: {artifact.path}{detail}")

    if not args.apply:
        print(
            "\nNo se realizaron cambios. Ejecuta con --apply para eliminar los artefactos detectados."
        )
        return 0

    print("\nEliminando artefactos obsoletos...\n")
    results = remove_artifacts(artifacts)
    exit_code = 0
    for artifact, success, error in results:
        detail = f" ({artifact.detail})" if artifact.detail else ""
        if success:
            status = "OK"
        else:
            status = f"ERROR: {error}" if error else "ERROR"
            exit_code = 1
        print(f" - {artifact.kind}: {artifact.path}{detail} -> {status}")

    if exit_code == 0:
        print("\nLimpieza completada. Vuelve a ejecutar 'pip install -e .' para reinstalar.")
    else:
        print("\nAlgunos artefactos no pudieron eliminarse. Revisa los mensajes anteriores.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
