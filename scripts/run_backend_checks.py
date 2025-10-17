#!/usr/bin/env python3
"""Run backend quality checks without stopping at the first failure."""
from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence


@dataclass
class TaskResult:
    title: str
    command: Sequence[str]
    returncode: int

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


COMMANDS: list[tuple[str, Sequence[str]]] = [
    ("Compilación del código Python", [sys.executable, "-m", "compileall", "src"]),
    ("Validación de dependencias", [sys.executable, "-m", "pip", "check"]),
]


def run_task(title: str, command: Sequence[str]) -> TaskResult:
    quoted = " ".join(shlex.quote(part) for part in command)
    print(f"\n==> {title}\n$ {quoted}")
    process = subprocess.run(command, text=True)
    print(f"-- Resultado: {'OK' if process.returncode == 0 else f'FALLO ({process.returncode})'}")
    return TaskResult(title=title, command=command, returncode=process.returncode)


def main() -> None:
    results = [run_task(title, command) for title, command in COMMANDS]
    failures = [result for result in results if not result.succeeded]

    print("\nResumen de comprobaciones:")
    for result in results:
        status = "✔" if result.succeeded else "✖"
        print(f"  {status} {result.title}")

    if failures:
        print("\nSe encontraron fallos en las comprobaciones anteriores.")
        sys.exit(1)


if __name__ == "__main__":
    main()
