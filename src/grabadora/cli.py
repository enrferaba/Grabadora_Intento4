"""Punto de entrada de línea de comandos para Grabadora Intento 4."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from .disclaimer import build_disclaimer
from .licensing import LicenseManager, LicensePayload, LicenseVerificationError
from .recorder import AudioRecorder, RecorderConfig, RecorderError

APP_NAME = "Grabadora Intento 4"
DEFAULT_DISCLAIMER_EMAIL = "legal@example.com"

app = typer.Typer(no_args_is_help=True, add_completion=False, help=APP_NAME)
licencia_app = typer.Typer(help="Herramientas para gestionar licencias.")
app.add_typer(licencia_app, name="licencia")
console = Console()


def _print_payload(payload: LicensePayload) -> None:
    table = Table(title="Licencia válida", box=box.ROUNDED, show_lines=True)
    table.add_column("Campo", style="cyan", no_wrap=True)
    table.add_column("Valor", style="green")
    table.add_row("Nombre", payload.name)
    table.add_row("Correo", payload.email)
    table.add_row("Producto", payload.product)
    table.add_row("Emitida", payload.issued_at.isoformat())
    table.add_row("Expira", payload.expires_at.isoformat())
    console.print(table)


@app.command()
def disclaimer(
    nombre_producto: str = typer.Option(APP_NAME, "--producto", help="Nombre comercial del producto."),
    responsable: str = typer.Option("Grabadora Team", "--responsable", help="Responsable legal."),
    correo: Optional[str] = typer.Option(DEFAULT_DISCLAIMER_EMAIL, "--correo", help="Correo de contacto."),
) -> None:
    """Muestra el descargo de responsabilidad estándar."""

    console.print(build_disclaimer(organization=responsable, product_name=nombre_producto, contact_email=correo))


@app.command()
def grabar(
    salida: Path = typer.Option(..., exists=False, dir_okay=False, writable=True, help="Ruta del archivo WAV de salida."),
    duracion: Optional[float] = typer.Option(None, min=0.0, help="Duración deseada en segundos."),
    sample_rate: int = typer.Option(48_000, min=8_000, help="Frecuencia de muestreo en Hz."),
    canales: int = typer.Option(2, min=1, max=8, help="Número de canales."),
    formato: str = typer.Option("int16", help="Formato de muestra soportado por sounddevice."),
    bloque_ms: int = typer.Option(50, min=10, max=1000, help="Tamaño del bloque de captura en milisegundos."),
    dispositivo: Optional[str] = typer.Option(None, help="Nombre o índice del dispositivo de entrada."),
    licencia: Optional[Path] = typer.Option(None, help="Archivo de licencia a validar antes de grabar."),
    clave_secreta: Optional[str] = typer.Option(None, help="Clave secreta para validar licencias."),
    aceptar_descargo: bool = typer.Option(
        False,
        "--aceptar-descargo",
        help="Salta la confirmación interactiva del descargo de responsabilidad.",
    ),
) -> None:
    """Inicia una sesión de grabación de audio."""

    payload = None
    if licencia:
        if not clave_secreta:
            raise typer.BadParameter("Debe proporcionar --clave-secreta para validar la licencia.", param_hint="--clave-secreta")
        manager = LicenseManager(secret_key=clave_secreta, product_name=APP_NAME)
        try:
            payload = manager.verify_file(licencia)
        except LicenseVerificationError as error:
            raise typer.BadParameter(str(error), param_hint="--licencia") from error
        _print_payload(payload)

    disclaimer_text = build_disclaimer(
        organization=payload.name if payload else "Grabadora Team",
        product_name=APP_NAME,
        contact_email=DEFAULT_DISCLAIMER_EMAIL,
    )

    console.rule("Condiciones de uso")
    console.print(disclaimer_text)

    if not aceptar_descargo:
        confirmado = Confirm.ask("¿Acepta expresamente el descargo de responsabilidad?")
        if not confirmado:
            raise typer.Abort()

    config = RecorderConfig(
        sample_rate=sample_rate,
        channels=canales,
        dtype=formato,
        block_duration_ms=bloque_ms,
        device=dispositivo,
        banner_lines=["Licencia verificada." if payload else "Modo sin licencia."],
    )

    recorder = AudioRecorder(config=config, console=console)

    try:
        recorder.record_to_file(
            salida,
            duration_seconds=duracion,
            license_text=json.dumps(payload.to_dict(), indent=2, ensure_ascii=False) if payload else None,
        )
    except RecorderError as error:
        raise typer.Exit(code=1) from error


@licencia_app.command("emitir")
def emitir(
    nombre: str = typer.Option(..., prompt="Nombre completo", help="Nombre del licenciatario."),
    correo: str = typer.Option(..., prompt="Correo electrónico", help="Correo del licenciatario."),
    dias: int = typer.Option(30, min=1, help="Días de validez."),
    clave_secreta: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
    salida: Path = typer.Option(Path("licencia.json"), help="Archivo donde se guardará la licencia."),
) -> None:
    """Emite una nueva licencia firmada."""

    payload = LicensePayload.issue(name=nombre, email=correo, product=APP_NAME, validity_days=dias)
    manager = LicenseManager(secret_key=clave_secreta, product_name=APP_NAME)
    manager.issue_license_file(payload, output_path=salida)
    console.print(f"[bold green]Licencia emitida correctamente en[/bold green] {salida}")


@licencia_app.command("verificar")
def verificar(
    archivo: Path = typer.Option(..., exists=True, dir_okay=False, readable=True, help="Archivo de licencia."),
    clave_secreta: str = typer.Option(..., prompt=True, hide_input=True),
) -> None:
    """Verifica una licencia existente."""

    manager = LicenseManager(secret_key=clave_secreta, product_name=APP_NAME)
    try:
        payload = manager.verify_file(archivo)
    except LicenseVerificationError as error:
        raise typer.BadParameter(str(error), param_hint="--archivo") from error
    _print_payload(payload)


@licencia_app.command("revocar")
def revocar(
    archivo: Path = typer.Option(..., exists=True, dir_okay=False, writable=True, help="Archivo de licencia."),
) -> None:
    """Elimina una licencia del disco."""

    manager = LicenseManager(secret_key="placeholder", product_name=APP_NAME)
    # No necesitamos validar la firma para eliminar el archivo; se utiliza una clave dummy.
    manager.revoke(archivo)
    console.print(f"[bold yellow]Licencia revocada y archivo eliminado:[/bold yellow] {archivo}")


if __name__ == "__main__":  # pragma: no cover
    app()
