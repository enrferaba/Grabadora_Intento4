"""Typer command line interface for administrative utilities."""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print
from rich.panel import Panel

from .disclaimer import DISCLAIMER_TEXT
from .license import issue_license, load_license, save_license, verify_license
from . import __version__

app = typer.Typer(add_completion=False, help="Herramientas administrativas para Transcriptor de FERIA")


@app.command("gui")
def launch_gui() -> None:
    """Inicia la interfaz gráfica."""
    from .gui import run

    run()


@app.command("disclaimer")
def show_disclaimer() -> None:
    """Muestra el descargo de responsabilidad que reciben los usuarios finales."""
    print(Panel.fit(DISCLAIMER_TEXT, title="Descargo de responsabilidad", border_style="yellow"))


@app.command("licencia-emitir")
def cmd_issue(
    nombre: str = typer.Option(..., help="Nombre completo del titular"),
    correo: str = typer.Option(..., help="Correo electrónico del titular"),
    dias: int = typer.Option(30, min=1, help="Días de validez"),
    clave_secreta: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True, help="Clave secreta privada"),
    nota: str = typer.Option("", help="Nota opcional"),
    salida: Path = typer.Option(Path("licencia.json"), help="Archivo de destino"),
) -> None:
    """Emite una nueva licencia firmada digitalmente."""
    blob = issue_license(holder=nombre, email=correo, validity_days=dias, secret=clave_secreta, note=nota or None)
    save_license(blob, salida)
    print(Panel.fit(json.dumps(blob, indent=2, ensure_ascii=False), title=f"Licencia guardada en {salida}", border_style="green"))


@app.command("licencia-verificar")
def cmd_verify(
    archivo: Path = typer.Option(..., exists=True, help="Archivo de licencia"),
    clave_secreta: str = typer.Option(..., prompt=True, hide_input=True, help="Clave secreta privada"),
) -> None:
    """Verifica una licencia existente."""
    blob = load_license(archivo)
    if verify_license(blob, clave_secreta):
        print(Panel.fit("Licencia válida", title="Resultado", border_style="green"))
    else:
        raise typer.Exit(code=1)


@app.command("version")
def version() -> None:
    """Muestra la versión instalada."""
    print(f"Transcriptor de FERIA v{__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
