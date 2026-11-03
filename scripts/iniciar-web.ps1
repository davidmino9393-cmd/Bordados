<#
Levanta la API real (con Ink/Stitch) y la web para convertir una imagen en un JEF, y abre el navegador.

Uso:  scripts\iniciar-web.cmd          (doble clic)
      powershell -File scripts\iniciar-web.ps1 [-NoBrowser] [-Config ruta] [-ApiPort 8000] [-WebPort 5173]

Cerrar la ventana, o Ctrl+C, detiene los dos servidores. Los registros quedan en services\api\.runtime\logs.
#>
param(
    [string]$Config = (Join-Path $PSScriptRoot '..\services\api\.runtime\api-config.json'),
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readyTimeoutS = 90

function Stop-WithMessage($message) {
    Write-Host "No se pudo iniciar: $message" -ForegroundColor Red
    exit 1
}

function Wait-Ready($url, $name) {
    $deadline = (Get-Date).AddSeconds($readyTimeoutS)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
            return
        } catch {
            # La API pide usuario y clave: un 401 también significa que ya responde.
            if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { return }
            Start-Sleep -Seconds 1
        }
    }
    Stop-WithMessage "$name no respondió en $readyTimeoutS s. Mirá los registros en services\api\.runtime\logs."
}

if (-not (Test-Path $Config)) {
    Stop-WithMessage "falta la configuración privada de la API ($Config). Ver services\api\docs\CONFIG.md."
}
$settings = Get-Content $Config -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($name in 'python_executable', 'inkstitch_executable') {
    if (-not (Test-Path $settings.$name)) { Stop-WithMessage "no existe $name ($($settings.$name)). Revisá la configuración." }
}
if (-not (Test-Path (Join-Path $root 'apps\web\node_modules'))) {
    Stop-WithMessage 'faltan las dependencias de la web. Corré una vez:  cd apps\web ; npm install'
}
foreach ($port in $ApiPort, $WebPort) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Stop-WithMessage "el puerto $port ya está en uso (¿ya está iniciado?)."
    }
}

$logs = Join-Path $root 'services\api\.runtime\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$env:EMBROIDERY_API_CONFIG = (Resolve-Path $Config).Path
$env:PYTHONPATH = (@('services\api', 'packages\contracts', 'workers\embroidery') | ForEach-Object { Join-Path $root $_ }) -join ';'
$env:PYTHONIOENCODING = 'utf-8'
$env:VITE_USE_MOCKS = 'false'
$env:API_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
# La web reenvía /api con estas credenciales: el navegador no pide usuario ni clave.
if ($settings.basic_username -and $settings.basic_password) {
    $pair = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$($settings.basic_username):$($settings.basic_password)"))
    $env:API_PROXY_AUTHORIZATION = "Basic $pair"
} elseif ($settings.service_token) {
    $env:API_PROXY_AUTHORIZATION = "Bearer $($settings.service_token)"
} else {
    Stop-WithMessage 'la configuración no tiene basic_username/basic_password ni service_token.'
}

$api = $null
$web = $null
try {
    $api = Start-Process -FilePath $settings.python_executable -PassThru -WindowStyle Hidden -WorkingDirectory $root `
        -ArgumentList '-m', 'uvicorn', 'embroidery_api.main:app', '--host', '127.0.0.1', '--port', $ApiPort `
        -RedirectStandardOutput (Join-Path $logs 'api.log') -RedirectStandardError (Join-Path $logs 'api.err.log')
    $web = Start-Process -FilePath 'npm.cmd' -PassThru -WindowStyle Hidden -WorkingDirectory (Join-Path $root 'apps\web') `
        -ArgumentList 'run', 'dev', '--', '--port', $WebPort, '--strictPort' `
        -RedirectStandardOutput (Join-Path $logs 'web.log') -RedirectStandardError (Join-Path $logs 'web.err.log')
    Wait-Ready "http://127.0.0.1:$ApiPort/api/v1/profiles" 'La API'
    Wait-Ready "http://localhost:$WebPort/" 'La web'

    Write-Host ''
    Write-Host "Listo: http://localhost:$WebPort" -ForegroundColor Green
    Write-Host 'Subí una imagen, elegí el tamaño y «Generar bordado». Para detener todo, cerrá esta ventana o presioná Ctrl+C.'
    if (-not $NoBrowser) { Start-Process "http://localhost:$WebPort" }
    while (-not $api.HasExited -and -not $web.HasExited) { Start-Sleep -Seconds 2 }
    Write-Host 'Uno de los servidores se detuvo; mirá los registros.' -ForegroundColor Yellow
} finally {
    foreach ($process in $api, $web) {
        if ($process -and -not $process.HasExited) { & taskkill /PID $process.Id /T /F | Out-Null }
    }
}
