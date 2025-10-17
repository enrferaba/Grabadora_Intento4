<#!
.SYNOPSIS
  Automatiza la instalación local, las comprobaciones básicas y los comandos de licencia.

.DESCRIPTION
  Ejecuta las tareas imprescindibles en Windows PowerShell para dejar el proyecto listo,
  valida que el backend se compila, instala el frontend y ofrece utilidades opcionales
  para emitir, verificar y consultar licencias.

.PARAMETER PrivateKey
  Ruta a la clave privada PEM para emitir tokens (opcional).

.PARAMETER PublicKey
  Ruta a la clave pública PEM para verificar tokens (opcional).

.PARAMETER LicenseToken
  Token JWT para verificar (opcional).

.EXAMPLE
  .\scripts\windows_quickstart.ps1 -PrivateKey .\clave.pem -PublicKey .\public.pem -LicenseToken "<jwt>"
#>
param(
    [string]$Python = "python",
    [string]$Node = "npm",
    [string]$PrivateKey = "",
    [string]$PublicKey = "",
    [string]$LicenseToken = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Action
    )
    Write-Host "`n=== $Title ===" -ForegroundColor Cyan
    & $Action
}

Invoke-Step -Title "Actualizando pip" -Action {
    & $Python -m pip install --upgrade pip
}

Invoke-Step -Title "Instalando dependencias del backend" -Action {
    & $Python -m pip install -e .
}

Invoke-Step -Title "Compilando código Python" -Action {
    & $Python -m compileall src
}

Invoke-Step -Title "Instalando dependencias del frontend" -Action {
    & $Node install --prefix ui-next
}

Invoke-Step -Title "Lint del frontend" -Action {
    & $Node run lint --prefix ui-next
}

Invoke-Step -Title "Estado de licencia instalada" -Action {
    & transcriptor licencia-estado
}

if ($PrivateKey -and $PublicKey) {
    Invoke-Step -Title "Emitiendo token de licencia" -Action {
        & transcriptor licencia-token-emitir `
            --llave-privada $PrivateKey `
            --correo "user@example.com" `
            --plan "pro" `
            --feature summary:redactado `
            --feature export:docx `
            --dias 30 `
            --seats 1
    }
}

if ($LicenseToken -and $PublicKey) {
    Invoke-Step -Title "Verificando token proporcionado" -Action {
        & transcriptor licencia-token-verificar `
            --token $LicenseToken `
            --llave-publica $PublicKey
    }
}

Write-Host "`nProceso completado. Ejecuta 'transcriptor launcher' para arrancar la app." -ForegroundColor Green
