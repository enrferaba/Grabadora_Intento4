"""Typer command line interface for administrative utilities."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print
from rich.panel import Panel

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
fastapi_app = None  # type: ignore[assignment]
_api_import_error: Optional[Exception] = None


if __package__ in (None, ""):
    if str(PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_ROOT))

    from transcriptor import __version__  # type: ignore
    from transcriptor.disclaimer import DISCLAIMER_TEXT  # type: ignore
    from transcriptor.license import issue_license, load_license, save_license, verify_license  # type: ignore
    from transcriptor.license_tokens import decode_token, issue_token  # type: ignore
    from transcriptor.license_service import LicenseManager  # type: ignore
    from transcriptor.launcher import run_launcher  # type: ignore
    from transcriptor.config import ConfigManager, PATHS  # type: ignore

    try:
        from transcriptor.api import app as _fastapi_app  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive feedback
        _api_import_error = exc
    else:
        fastapi_app = _fastapi_app
else:
    from . import __version__
    from .disclaimer import DISCLAIMER_TEXT
    from .license import issue_license, load_license, save_license, verify_license
    from .license_tokens import decode_token, issue_token
    from .license_service import LicenseManager
    from .launcher import run_launcher
    from .config import ConfigManager, PATHS

    try:
        from .api import app as _fastapi_app
    except Exception as exc:  # pragma: no cover - defensive feedback
        _api_import_error = exc
    else:
        fastapi_app = _fastapi_app

app = typer.Typer(add_completion=False, help="Herramientas administrativas para Transcriptor de FERIA")


@app.command("gui")
def launch_gui() -> None:
    """Inicia la interfaz gráfica."""
    from .gui import run

    run()


@app.command("api")
def run_api(
    host: str = typer.Option("127.0.0.1", help="Host de escucha"),
    port: int = typer.Option(4814, help="Puerto HTTP para el backend"),
    reload: bool = typer.Option(False, help="Activa autoreload (solo desarrollo)"),
) -> None:
    """Arranca el backend FastAPI local."""
    if fastapi_app is None:
        typer.secho(
            "El backend FastAPI no pudo importarse. Revisa la instalación (falta:"
            f" {_api_import_error})",
            fg="red",
            err=True,
        )
        raise typer.Exit(code=1)
    import uvicorn

    uvicorn.run(fastapi_app, host=host, port=port, reload=reload, log_level="info")


@app.command("launcher")
def run_launcher_cmd() -> None:
    """Inicia el launcher con bandeja del sistema."""
    if _api_import_error is not None:
        typer.secho(
            "No se puede iniciar el launcher porque el backend no cargó:"
            f" {_api_import_error}",
            fg="red",
            err=True,
        )
        raise typer.Exit(code=1)
    run_launcher()


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
        print(Panel.fit("Licencia inválida o expirada", title="Resultado", border_style="red"))
        raise typer.Exit(code=1)


@app.command("licencia-token-emitir")
def cmd_issue_token(
    llave_privada: Path = typer.Option(..., exists=True, help="Ruta al PEM con la clave privada RS256/ES256"),
    correo: str = typer.Option(..., help="Correo del titular"),
    plan: str = typer.Option("pro", help="Nombre del plan"),
    feature: list[str] = typer.Option(
        ["summary:redactado", "summary:extractivo", "export:markdown", "export:docx", "export:json"],
        help="Lista de features habilitadas",
    ),
    seats: int = typer.Option(1, min=1, help="Número de dispositivos permitidos"),
    dias: int = typer.Option(30, min=1, help="Días de validez"),
    gracia: int = typer.Option(7, min=0, help="Días de gracia offline"),
    device_hash: str = typer.Option("", help="Huella concreta del dispositivo (opcional)"),
) -> None:
    """Genera un token de licencia firmado."""
    token = issue_token(
        private_key_path=llave_privada,
        holder_email=correo,
        plan=plan,
        features=feature,
        seats=seats,
        expires_in_days=dias,
        grace_days=gracia,
        device_hash=device_hash or None,
    )
    payload = json.dumps(token.payload, indent=2, ensure_ascii=False)
    print(Panel.fit(payload, title="Payload", border_style="cyan"))
    print(Panel.fit(token.token, title="Token JWT", border_style="green"))


@app.command("licencia-token-verificar")
def cmd_verify_token(
    token: str = typer.Option(..., help="Token JWT a verificar"),
    llave_publica: Path = typer.Option(..., exists=True, help="Clave pública PEM"),
) -> None:
    """Verifica un token firmado y muestra su contenido."""
    payload = decode_token(token, llave_publica)
    print(Panel.fit(json.dumps(payload, indent=2, ensure_ascii=False), title="Token válido", border_style="green"))


@app.command("licencia-estado")
def cmd_license_status() -> None:
    """Muestra el estado de la licencia instalada en este equipo."""
    manager = LicenseManager(ConfigManager(PATHS.config_file))
    status = manager.status()
    features = "\n".join(f"- {feature}" for feature in sorted(status.features)) or "Sin features"
    body = (
        f"Plan: {status.plan}\n"
        f"Activa: {'sí' if status.active else 'no'}\n"
        f"En gracia: {'sí' if status.in_grace else 'no'}\n"
        f"Caducidad: {status.expires_at.isoformat() if status.expires_at else 'desconocida'}\n"
        f"Motivo: {status.reason or 'OK'}\n"
        f"Features:\n{features}"
    )
    print(Panel.fit(body, title="Estado de licencia", border_style="blue"))


@app.command("version")
def version() -> None:
    """Muestra la versión instalada."""
    print(f"Transcriptor de FERIA v{__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
