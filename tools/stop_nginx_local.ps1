param(
    [string]$NginxDir = "C:\nginx"
)

$nginxExe = Join-Path $NginxDir "nginx.exe"
if (!(Test-Path $nginxExe)) {
    Write-Error "Nginx not found at: $nginxExe. Install Nginx or pass -NginxDir."
    exit 1
}

& $nginxExe -p "$NginxDir\" -s stop
