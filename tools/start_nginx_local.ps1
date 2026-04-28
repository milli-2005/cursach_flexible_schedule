param(
    [string]$NginxDir = "C:\nginx"
)

$nginxExe = Join-Path $NginxDir "nginx.exe"
if (!(Test-Path $nginxExe)) {
    Write-Error "Nginx not found at: $nginxExe. Install Nginx or pass -NginxDir."
    exit 1
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$confPath = Join-Path $projectRoot "schedule_optimizer\nginx\nginx.local.conf"

if (!(Test-Path $confPath)) {
    Write-Error "Config not found: $confPath"
    exit 1
}

# Windows nginx may fail on Unicode paths (e.g. Cyrillic folders).
# Copy config into nginx/conf (ASCII path) and run from there.
$targetConfDir = Join-Path $NginxDir "conf"
if (!(Test-Path $targetConfDir)) {
    Write-Error "Nginx conf directory not found: $targetConfDir"
    exit 1
}

$targetConf = Join-Path $targetConfDir "nginx.local.generated.conf"
Copy-Item -LiteralPath $confPath -Destination $targetConf -Force

& $nginxExe -p "$NginxDir\" -c "conf/nginx.local.generated.conf"
if ($LASTEXITCODE -eq 0) {
    Write-Output "Nginx started. Open http://127.0.0.1:8000"
}
