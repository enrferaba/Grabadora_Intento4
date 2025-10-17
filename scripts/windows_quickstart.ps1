<#!
.SYNOPSIS
  Automatiza la instalación local, las comprobaciones básicas y los comandos de licencia.

.DESCRIPTION
  Ejecuta las tareas imprescindibles en Windows PowerShell para dejar el proyecto listo,
  valida que el backend se compila y que las dependencias están en orden, instala el frontend
  y ejecuta sus comprobaciones sin detenerse en el primer fallo.

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

$script:StepResults = @()
$script:BackendInstalled = $false

function Add-StepResult {
    param(
        [string]$Title,
        [bool]$Success,
        [string]$Message = "",
        [bool]$Optional = $false
    )

    $script:StepResults += [pscustomobject]@{
        Title = $Title
        Success = $Success
        Message = $Message
        Optional = $Optional
    }
}

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Action,
        [switch]$Optional
    )

    Write-Host "`n=== $Title ===" -ForegroundColor Cyan
    try {
        & $Action
        Add-StepResult -Title $Title -Success $true -Optional:$Optional
        return $true
    }
    catch {
        $errorMessage = $_.Exception.Message
        Write-Host "Fallo en '$Title': $errorMessage" -ForegroundColor Red
        Add-StepResult -Title $Title -Success $false -Message $errorMessage -Optional:$Optional
        if (-not $Optional) {
            return $false
        }
        return $true
    }
}

Invoke-Step -Title "Actualizando pip" -Action {
    & $Python -m pip install --upgrade pip
} | Out-Null

Invoke-Step -Title "Instalando dependencias del backend" -Action {
    & $Python -m pip install -e .
    $script:BackendInstalled = $true
} | Out-Null

Invoke-Step -Title "Comprobaciones del backend" -Action {
    & $Python scripts/run_backend_checks.py
} | Out-Null

Invoke-Step -Title "Instalando dependencias del frontend" -Action {
    & $Node install --prefix ui-next
} | Out-Null

Invoke-Step -Title "Comprobaciones del frontend" -Action {
    & $Node run check --prefix ui-next
} | Out-Null

if ($script:BackendInstalled) {
    Invoke-Step -Title "Estado de licencia instalada" -Action {
        & transcriptor licencia-estado
    } | Out-Null
} else {
    Add-StepResult -Title "Estado de licencia instalada" -Success $true -Message "Omitido (backend no instalado)" -Optional $true
}

if ($PrivateKey -and $PublicKey) {
    if ($script:BackendInstalled) {
        Invoke-Step -Title "Emitiendo token de licencia" -Action {
            & transcriptor licencia-token-emitir `
                --llave-privada $PrivateKey `
                --correo "user@example.com" `
                --plan "pro" `
                --feature summary:redactado `
                --feature export:docx `
                --dias 30 `
                --seats 1
        } | Out-Null
    } else {
        Add-StepResult -Title "Emitiendo token de licencia" -Success $true -Message "Omitido (backend no instalado)" -Optional $true
    }
}

if ($LicenseToken -and $PublicKey) {
    if ($script:BackendInstalled) {
        Invoke-Step -Title "Verificando token proporcionado" -Action {
            & transcriptor licencia-token-verificar `
                --token $LicenseToken `
                --llave-publica $PublicKey
        } | Out-Null
    } else {
        Add-StepResult -Title "Verificando token proporcionado" -Success $true -Message "Omitido (backend no instalado)" -Optional $true
    }
}

Write-Host "`nResumen de pasos:" -ForegroundColor Cyan
foreach ($result in $StepResults) {
    $mark = if ($result.Success) { "✔" } else { "✖" }
    $message = if ($result.Message) { " - $($result.Message)" } else { "" }
    Write-Host "  $mark $($result.Title)$message"
}

$failures = $StepResults | Where-Object { -not $_.Success }
$blockingFailures = $failures | Where-Object { -not $_.Optional }
if ($blockingFailures.Count -gt 0) {
    Write-Host "`nProceso completado con errores." -ForegroundColor Red
    exit 1
}

Write-Host "`nProceso completado. Ejecuta 'transcriptor launcher' para arrancar la app." -ForegroundColor Green
exit 0
